The 'Library Import' feature makes it possible to import an existing library of media files into Kapowarr. You could have an existing library because you used a different software before, or because you downloaded media manually. In that case, Library Import makes it easy to start using Kapowarr. You can find the Library Import feature in the web-UI at Volumes -> Library Import.

## Proposal

When you run Library Import, it will search for files in your root folders that aren't matched to any issues yet. It will then try to find the volume that the file is for on ComicVine. This list of files and ComicVine matches is presented to you (a.k.a. Library Import proposal). You can then change the matches in case Kapowarr guessed incorrectly. You can choose to apply the changed match to only the file, or to all files for the volume.

On the start screen, there are some settings that change the behaviour of Library Import:

- **Max folders scanned**  
Limit the proposal to this amount of folders (roughly equal to the amount of volumes). Setting this to a large amount increases the chance of hitting the ComicVine rate limit.

- **Apply limit to parent folder**  
Apply the folder limit (see previous bullet) to the parent folder instead of the folder. Enable this when each issue has its own sub-folder.

- **Only match English volumes**  
When Kapowarr is searching on ComicVine for a match to the file, only allow the match when it's an English release; it won't allow translations.

- **Folder(s) to scan**  
Allows you to supply a specific folder in a root folder to scan, instead of all root folders. Supports glob patterns (e.g. `/comics/Star Wars*`).

## Importing

When you are happy with the proposal, you have two options: 'Import' and 'Import and Rename'. Clicking 'Import' will make Kapowarr add all the volumes and set their volume folder to the folder that the file is in. Clicking 'Import and Rename' will make Kapowarr add all the volumes and move the files into the automatically generated volume folder, after which it will rename them. If a volume is already added to the library, then clicking 'Import' will move the matched files to the volume folder. Clicking 'Import and Rename' will move the matched files to the volume folder and rename them then.
