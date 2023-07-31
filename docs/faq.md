# FAQ

## Does Kapowarr support XYZ?

"XYZ" can be "Magazines" or "Manga" or something else. For now, there is a simple answer: if it can be found on ComicVine, you can add it to Kapowarr (and use features like renaming and unzipping). If getcomics offers downloads for it, you can also download for it.

## When will XYZ be added?

"XYZ" can be "Library Import" or "Exporting metadata" or something else. First, check out the [project board](https://github.com/users/Casvt/projects/5) to see if it's already on there and if so, at what stage it is. If it's not, check if a feature request is already made for it on the [issues page](https://github.com/Casvt/Kapowarr/issues) and otherwise make a feature request for it there.

## Kapowarr unable to open database file

If using Kapowarr with a mapped folder for the app-db rather than a docker volume, then Kapowarr will need to have permission on the folder being mapped in order to function.  
The simplest way to achieve this is to use `chmod` on the folder being mapped in to give read, write, and execute permissions on the folder ('rwx') for the relevant user you have Kapowarr running as.
