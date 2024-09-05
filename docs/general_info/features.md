# Features

## Library Import

The feature 'Library Import' makes it possible to import an existing library into Kapowarr. You could have an existing library because you used a different software before, or because you downloaded media manually. In that case, Library Import makes it easy to start using Kapowarr.

### Proposal

When you run Library Import, it will search for files in your root folders that aren't matched to any issues yet. It will then try to find the volume for the file on CV. This list of files and CV matches gets presented to you (a.k.a. Library Import proposal). You can then change the matches, in case Kapowarr guessed incorrectly. You can choose to apply the changed match to only the file, or to all files for the volume.

On the start screen, there are some settings that change the behaviour of Library Import:

- **Max folders scanned**: Limit the proposal to this amount of folders (roughly equal to the amount of volumes). Setting this to a large amount increases the chance of hitting the [CV rate limit](../other_docs/rate_limiting.md).
- **Apply limit to parent folder**: Apply the folder limit (prev. bullet) to the parent folder instead of the folder. Enable this when each issue has it's own sub-folder.
- **Only match english volumes**: When Kapowarr is searching on CV for a match for a file, only allow the match when it's an english release. So it won't allow translations.
- **Folder(s) to scan**: Allows you to supply a specific folder to scan, instead of all root folders. Supports glob patterns (e.g. `/content/Star Wars*`).

### Importing

When you are happy with the proposal, you have two options: 'Import' and 'Import and Rename'. Clicking 'Import' will make Kapowarr add all the volumes and set their volume folder to the folder that the file is in. Clicking 'Import and Rename' will make Kapowarr add all the volumes and move the files into the automatically generated volume folder, after which it will rename them.

### Implementation Details

When 'Import' is used, the volume folder that is set is the 'lowest common folder'. This is the lowest folder that still contains all files that are matched to that volume.

If the CV rate limit is reached halfway through the proposal, the unhandled files will have no match. Files that don't have a match linked to them will be ignored when importing, regardless of the state of the checkbox for that file. It's advised to wait a few minutes and then do another run.

If you imported files but certain ones pop up again in the next run, see the [FAQ on this topic](../other_docs/faq.md#why-do-certain-files-pop-up-in-the-library-import-even-though-i-just-imported-them).
