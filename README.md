```
> KODI_ADDON    (/home/sonne/.ansible/plugins/modules/kodi_addon.py)

        This module installs an addon and its dependencies into kodi,
        optionally enabling it

  * This module is maintained by The Ansible Community
OPTIONS (= is mandatory):

- kodi_home
        The data directory for kodi. Defaults to ~<kodi_user>/.kodi
        [Default: ~kodi_user/.kodi]
        type: str

= kodi_release
        This is the kodi release that the addon will be downloaded
        for, such as 'leia' or 'krypton'.

        type: str

- kodi_user
        The username that kodi is run as. Used to establish the
        ownership of the addon data. Defaults to kodi.
        [Default: kodi]
        type: str

= name
        This is the name in the module as kodi knows it. For example
        if you want 'SoundCloud' the name will be
        'plugin.audio.soundcloud'.

        type: str

- state
        `present'/`enabled' will ensure the addon and its dependencies
        are installed and enabled.
        `disabled' will install the module and its dependencies if
        missing, and ensure it's disabled. Newly installed
        dependencies will be left disabled. Present dependencies are
        left untouched.
        `absent' will remove the addon completely. Dependencies are
        left untouched.
        [Default: enabled]
        type: str


AUTHOR: Alessandro Grassi (@agrassi)
        METADATA:
          status:
          - preview
          supported_by: community
        

EXAMPLES:

# Install the TVDB plugin on kodi installed on raspbian
- name: TVDB is installed
  kodi_addon:
    name: metadata.tvdb.com
    kodi_user: kodi
    kodi_home: /home/kodi/.kodi
    enabled: true
    kodi_release: leia


```
