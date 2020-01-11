#!/usr/bin/python

# Copyright: (c) 2020, Alessandro Grassi <alessandro@aggro.it>
# 2-Clause BSD License (see COPYING or https://opensource.org/licenses/BSD-2-Clause)

from ansible.module_utils.basic import AnsibleModule
from xml.etree import ElementTree as etree
# urlretreive() is in different places in python 2 and 3
try:
    from urllib import urlretrieve as download
except ImportError:
    from urllib.request import urlretrieve as download
from os.path import basename, exists, join as path_join
from os import walk, chown
from shutil import rmtree as rm_rf
from zipfile import ZipFile as zip
from pwd import getpwnam
from tempfile import NamedTemporaryFile as mktemp
from gzip import open as gunzip
from sqlite3 import connect as sqlite3_connect

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

SUPPORTED_RELEASES = [
    'krypton',
    'leia',
    'matrix'
]

DOCUMENTATION = r'''
---
module: kodi_addon

short_description: Install an addon within kodi

version_added: "2.9"

description:
    - "This module installs an addon and its dependencies into kodi, optionally enabling it"

options:
    name:
        description:
            - This is the name in the module as kodi knows it. For example if you want 'SoundCloud' the name will be 'plugin.audio.soundcloud'.
        type: str
        required: true

    kodi_user:
        description:
            - The username that kodi is run as. Used to establish the ownership of the addon data. Defaults to kodi.
        required: false
        default: kodi
        type: str

    state:
        description:
          - C(present)/C(enabled) will ensure the addon and its dependencies are installed and enabled.
          - C(disabled) will install the module and its dependencies if missing, and ensure it's disabled. Newly installed dependencies will be left disabled. Present dependencies are left untouched.
          - C(absent) will remove the addon completely. Dependencies are left untouched.
        required: false
        type: str
        default: enabled

    kodi_release:
        description:
            - This is the kodi release that the addon will be downloaded for, such as 'leia' or 'krypton'.
        type: str
        required: true

    kodi_home:
        description:
            - The data directory for kodi. Defaults to ~<kodi_user>/.kodi
        required: false
        default: ~kodi_user/.kodi
        type: str

author:
    - Alessandro Grassi (@agrassi)
'''

EXAMPLES = '''
# Install the TVDB plugin on kodi installed on raspbian
- name: TVDB is installed
  kodi_addon:
    name: metadata.tvdb.com
    kodi_user: kodi
    kodi_home: /home/kodi/.kodi
    enabled: true
    kodi_release: leia
'''


def is_enabled(addon, home):

    db = sqlite3_connect("%s/userdata/Database/Addons27.db" % (home))
    cursor = db.cursor()

    id = cursor.execute(
        "SELECT 1 FROM installed WHERE addonID = '%s' AND enabled"
        % (addon)
    ).fetchone()
    db.close()

    return True if id else False


def is_in_db(addon, home):

    db = sqlite3_connect("%s/userdata/Database/Addons27.db" % (home))
    cursor = db.cursor()

    id = cursor.execute(
        "SELECT id FROM installed WHERE addonID = '%s'"
        % (addon)
    ).fetchone()
    db.close()

    return True if id else False


def update_db(addon, home, enabled):

    # Check if the addon is in the db already and set the enable flag
    its_there = is_in_db(addon, home)
    en = 1 if enabled else 0

    # Open the addon database
    db = sqlite3_connect("%s/userdata/Database/Addons27.db" % (home))
    cursor = db.cursor()

    # Add the addon to the database if necessary, enabling it if requested
    if its_there:
        cursor.execute(
            "UPDATE installed SET enabled = %s WHERE addonID = '%s'"
            % (en, addon)
        )
    else:
        cursor.execute(
            "INSERT INTO installed select (MAX(id)+1),'%s',1,datetime(),NULL,NULL,'' FROM installed;"
            % (addon)
        )

    db.commit()
    db.close()


def install_addon(repo_url, addons, addon, user, home, release, enabled):

    # Avoid installing already existing addons
    if exists("%s/addons/%s" % (home, addon)) and enabled:
        update_db(addon, home, True)
        return

    # Check the xml definition for package dependencies and install them first
    dependencies = addons.findall('addon[@id="%s"]/requires/import' % (addon))
    for dep in dependencies:
        dep_name = dep.get('addon')
        # 'xbmc.*' are not really addons
        if dep_name.split('.')[0] != 'xbmc':
            install_addon(repo_url, addons, dep_name, user, home, release, enabled)

    # Find the location for the .zip file in the xml definition
    addon_path = addons.find('addon[@id="%s"]/extension/path' % (addon)).text

    # Compute full url for the zip file
    zip_url = '%s/%s' % (repo_url, addon_path)

    # We save the zip file in packages/ as kodi does
    zip_base = basename(addon_path)
    zip_local = '%s/addons/packages/%s' % (home, zip_base)
    download(zip_url, zip_local)

    # Extract the zip in the addon directory
    zip(zip_local, 'r').extractall("%s/addons/" % (home))

    # chown -R to the user
    pwdata = getpwnam(user)
    for root, dirs, files in walk("%s/addons/%s" % (home, addon), topdown=False):
        for name in files:
            chown(path_join(root, name), pwdata.pw_uid, pwdata.pw_gid)
        for name in dirs:
            chown(path_join(root, name), pwdata.pw_uid, pwdata.pw_gid)

    chown("%s/addons/%s" % (home, addon), pwdata.pw_uid, pwdata.pw_gid)

    update_db(addon, home, enabled)


def remove_addon(addon, home):
    changed = False
    if exists("%s/addons/%s" % (home, addon)):
        rm_rf("%s/addons/%s" % (home, addon))
        changed = True
    db = sqlite3_connect("%s/userdata/Database/Addons27.db" % (home))
    cursor = db.cursor()
    id = cursor.execute(
        "SELECT id FROM installed WHERE addonID = '%s'"
        % (addon)
    ).fetchone()
    if id:
        cursor.execute("DELETE FROM installed WHERE idAddon = '%s'" % (addon))
        changed = True
        db.commit()
    db.close()
    return changed


def run_module():
    # seed the result dict in the object
    result = dict(
        changed=True,
    )

    # define available arguments/parameters a user can pass to the module
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(
                type='str',
                default='enabled',
                required=False,
                choices=[
                    'present',
                    'absent',
                    'enabled',
                    'disabled'
                ]
            ),
            name=dict(
                type='str',
                required=True
            ),
            kodi_user=dict(
                type='str',
                required=False,
                default='kodi'
            ),
            kodi_home=dict(
                type='str',
                required=False,
                default=''
            ),
            kodi_release=dict(
                type='str',
                required=True
            ),
        ),
        supports_check_mode=True
    )

    # We only work with releases that have the database version 27
    # See: https://kodi.wiki/view/Databases#Database_Versions
    if not SUPPORTED_RELEASES.__contains__(module.params['kodi_release']):
        module.fail_json(
            msg='Unsupported kodi release. Supported: %s' % (SUPPORTED_RELEASES),
            **result
        )

    # Seed the default kodi home if not supplied
    if module.params['kodi_home']:
        kodi_home = module.params['kodi_home']
    else:
        kodi_home = "%s/.kodi" % (getpwnam(module.params['kodi_user']).pw_dir)

    # Seed the default kodi repository
    kodi_repo = 'http://mirrors.kodi.tv/addons/%s/addons.xml.gz' % (module.params['kodi_release'])

    # Shortcut for the actual repository, computed removing 'addons.xml(.gz)'
    repo_base = '/'.join(kodi_repo.split('/')[0:-1])

    if module.params['state'] == 'absent':

        if module.check_mode:
            # We would only remove the addon if it's in the directory,
            #   or if it has traces in the db
            result['changed'] = (
                exists("%s/addons/%s" % (kodi_home, module.params['name']))
                or is_in_db(module.params['name'], kodi_home)
            )
            module.exit_json(**result)

        result['changed'] = remove_addon(kodi_home, module.params['name'])
        module.exit_json(**result)

    elif module.params['state'] == 'disabled':
        enabled = False
    elif module.params['state'] in ['present', 'enabled']:
        enabled = True

    # If the directory already exists and the enabled status is as desired, then we have nothing to do
    if exists("%s/addons/%s" % (kodi_home, module.params['name'])):
        if is_enabled(module.params['name'], kodi_home) == enabled:
            result['changed'] = False
            module.exit_json(**result)

    addons_xml = mktemp()

    # Download the repository definition, uncompressing it if necessary
    # This check is left from an attempt to support multiple repositories which might be retried, no need to delete it.
    if kodi_repo.split('.')[-1] == 'gz':
        addons_xml_gz = mktemp()
        download(kodi_repo, addons_xml_gz.name)
        addons_xml.seek(0)
        addons_xml.truncate()
        addons_xml.write(gunzip(addons_xml_gz.name).read())
        addons_xml.flush()
    else:
        download(kodi_repo, addons_xml.name)

    # Load the actual xml
    addons = etree.parse(addons_xml.name)

    install_addon(repo_base, addons, module.params['name'], module.params['kodi_user'], kodi_home, module.params['kodi_release'], enabled)

    result['changed'] = True
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
