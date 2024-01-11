# FAQ

## Does Kapowarr support XYZ?

"XYZ" can be "Magazines" or "Manga" or something else. For now, there is a simple answer: if it can be found on ComicVine, you can add it to Kapowarr (and use features like renaming and converting). If GetComics offers downloads for it, you can also download for it.

## When will XYZ be added?

"XYZ" can be "Usenet support" or "Exporting metadata" or something else. First, check out the [project board](https://github.com/users/Casvt/projects/5) to see if it's already on there and if so, at what stage it is. If it's not, check if a feature request is already made for it on the [issues page](https://github.com/Casvt/Kapowarr/issues) and otherwise make a feature request for it there.

## Kapowarr unable to open database file

If you are using Kapowarr with a mapped folder for the app-db rather than a docker volume, then Kapowarr will need to have permissions on the folder being mapped in order to function.  
The simplest way to achieve this is to give read, write, and execute permissions on the folder ('rwx'), and change ownership of the folder to the user that runs the docker container (usually user 1000).  

This can be achieved by running `chown 1000 /mapped/folder` to set the ownership, and `chmod 770 /mapped/folder` to set the permissions.  
If you are mapping in `/opt/kapowarr/` (as in our installation example), these commands would be `chown 1000 /opt/kapowarr/` and `chmod 770 /opt/kapowarr`, respectively.

_If you are using an alternate folder, or an alternate user, switch out the relevant detail in the examples_.
