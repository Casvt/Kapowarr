In the 'Media Management' sub-section, you can find settings related to the placement and naming of files.

## File Naming

### Rename Downloaded Files

When a file is downloaded, this setting decides whether it should be renamed or not. If the checkbox is unchecked, the default filename is used. If the checkbox is checked, it is renamed following the formats set below. This does not affect the naming of the volume folder, only the filename itself.

| Setting | Example Result |
| ------- | -------------- |
| Disabled | Deadpool 01 (of 04) (1994) (digital) (Minutemen-Slayer).cbr |
| Enabled | Deadpool (1994) Volume 02 Issue 001.cbr |

### Replace Illegal Characters

Instead of removing illegal characters from the filename, replace them smartly with a dash. Depending on the place, spaces might be put before, after or around the dash.

| Setting | Example Result |
| ------- | -------------- |
|  | Batman/Superman: World's Finest |
| Disabled | BatmanSuperman Worlds Finest |
| Enabled | Batman-Superman - Worlds Finest |

### Volume Folder Naming

The naming format for the volume folder. Keep in mind that the resulting name could differ slightly from the format, in the case that certain values of variables contain illegal characters. For example, if the `{series_name}` is "What If...", the resulting name will have "What If" as its value, because the character `.` is not allowed at the end of the name in Windows. This also applies to the other naming formats in this section.

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | The Incredibles |
	| {clean_series_name} | Incredibles, The |
	| {volume_number} | 01 |
	| {comicvine_id} | 2127 |
	| {year} | 1994 |
	| {publisher} | DC Comics |
	| {special_version} | One-Shot |

| Example Value | Example Resulting Name |
| ------------- | -------------- |
| {series_name}/Volume {volume_number} ({year}) | Deadpool/Volume 01 (1994) |
| {clean_series_name} - Volume \{year\} | Incredibles, The - Volume 1994 |

### File Naming

The naming format for the file itself.

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | The Incredibles |
	| {clean_series_name} | Incredibles, The |
	| {volume_number} | 01 |
	| {comicvine_id} | 2127 |
	| {year} | 1994 |
	| {publisher} | DC Comics |
	| {issue_comicvine_id} | 6422 |
	| {issue_number} | 001 |
	| {issue_title} | Spider-Man; Spider-Man Vs. The Chameleon |
	| {issue_release_date} | 1963-03-01 |
	| {issue_release_year} | 1963 |

| Example Value | Example Resulting Name |
| ------------- | -------------- |
| {series_name} ({year}) Volume {volume_number} Issue \{issue_number\} | Deadpool (1994) Volume 01 Issue 002 |
| Issue {issue_number} - {issue_title} ({issue_release_date}) [issue_comicvine_id] | Issue 001 - Spider-Man; Spider-Man Vs. The Chameleon (1963-03-01) [6422] |

### File Naming For Issues Without Title

The naming format for the file, in the case that the issue does not have a title.

If the value of the setting [File Naming](#file-naming_1) uses the issue title, it will most likely look ugly when the issue doesn't have a title. For example, if your format is `Issue {issue_number} - {issue_title}`, but the issue doesn't have a title, it will result in a file like `Issue 5 - Unknown.cbr`. For that scenario, this setting exists. Here you can set an alternative format for when the issue doesn't have a title.

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | The Incredibles |
	| {clean_series_name} | Incredibles, The |
	| {volume_number} | 01 |
	| {comicvine_id} | 2127 |
	| {year} | 1994 |
	| {publisher} | DC Comics |
	| {issue_comicvine_id} | 6422 |
	| {issue_number} | 001 |
	| {issue_release_date} | 1963-03-01 |
	| {issue_release_year} | 1963 |

| Example Value | Example Resulting Name |
| ------- | -------------- |
| {series_name} ({year}) Volume {volume_number} Issue \{issue_number\} | Deadpool (1994) Volume 01 Issue 002 |
| Issue {issue_number} ({issue_release_date}) [issue_comicvine_id] | Issue 001 (1963-03-01) [6422] |

### File Naming For Special Versions

The naming format for the file itself (if it's a special version, like a TPB, one shot or hard cover).

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | Silver Surfer Rebirth |
	| {clean_series_name} | Silver Surfer Rebirth |
	| {volume_number} | 01 |
	| {comicvine_id} | 147555 |
	| {year} | 2022 |
	| {publisher} | Marvel |
    | {special_version} | One-Shot |

| Example Value | Example Resulting Name |
| ------- | -------------- |
| {series_name} ({year}) Volume {volume_number} \{special_version\} | Silver Surfer Rebirth (2022) Volume 01 TPB |

### File Naming For "Volume As Issue"

The naming format for the file itself (if it's a Volume As Issue, so an issue named "Volume N").

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | The Incredibles |
	| {clean_series_name} | Incredibles, The |
	| {volume_number} | 01 |
	| {comicvine_id} | 2127 |
	| {year} | 1994 |
	| {publisher} | DC Comics |
	| {issue_comicvine_id} | 6422 |
	| {issue_number} | 002 |
	| {issue_title} | Spider-Man; Spider-Man Vs. The Chameleon |
	| {issue_release_date} | 1963-03-01 |
	| {issue_release_year} | 1963 |

| Example Value | Example Resulting Name |
| ------------- | -------------- |
| {series_name} ({year}) Volume \{issue_number\} | Reign of X (1994) Volume 002 - 003 |
| Volume {volume_number} Issue {issue_number} ({issue_release_date}) [issue_comicvine_id] | Volume 01 Issue 002 - 003 (1963-03-01) [6422] |

### Use Long Special Version Labels

Whether or not to use, for example, 'One-Shot' instead of 'OS' [in the filename for Special Versions](#file-naming-for-special-versions). The term 'TPB' will always stay 'TPB'.

### Issue Padding

How issue numbers should be padded with leading zeros. This is useful in the case of file sorting, as many operating systems sort alphabetically, instead of alphanumerically. To them, because '1' is lower than '2', '10' comes before '2'. To get around this, pad the numbers with leading zeroes.

Options are:

- x (no padding, i.e. 1, 2...99, 100)
- 0x (2 digits, i.e. 01, 02...99, 100)
- 00x (3 digits, i.e. 001, 002...099, 100)
- 000x (4 digits, i.e. 0001, 0002...0099, 0100)

### Volume Padding

How volume numbers should be padded, similarly to the [Issue Padding](#issue-padding) setting.

Options are:

- x (no padding, i.e. 1, 2...99, 100)
- 0x (2 digits, i.e. 01, 02...99, 100)
- 00x (3 digits, i.e. 001, 002...099, 100)

## Folders

### Create Empty Volume Folders

When scanning for files, if a volume folder doesn't exist, create it.

### Delete Empty Folders

When scanning for files, delete any empty folders that are found in the volume folder. If "Create Empty Volume Folders" is disabled and the volume folder is empty, it'll also be deleted.

## File Management

### Unmonitor Deleted Issues

If an issue had files matched to it, but all have been deleted, automatically unmonitor the issue.

### Change File Date

Change the date of the file in the file system by setting it to the release date of the issue that the file is for. Use the button below it to apply the setting to all existing files.

- Linux: modification time and access time
- Windows: modification time and creation time
- MacOS: modification time, access time and creation time

### Chmod Folder

Set the filesystem permissions of the volume folders, all sub-folders and all files in the volume folders. Give the permissions in the octal 'chmod' format (e.g. '755'). The version of the permissions _with_ execute bits is applied to the folders and one _without_ execute bits is applied to the files. Use the button below it to apply the setting to all existing files.

### Chown Group

Set the filesystem group owner of the volume folders, all sub-folders and all files in the volume folders. Give the group name or ID (e.g. 'media' or '1001'). The user that is running Kapowarr must be part of the group. Use the button below it to apply the setting to all existing files.

## Converting

The "converting" feature allows you to change the format of your files (e.g. from cbr to cbz). Extracting archive files also falls under "converting".

### Convert/Extract Downloaded Files

This setting dictates whether Kapowarr should automatically convert downloaded files. As mentioned before, this also covers extracting archive files. Kapowarr will follow the [format preference](#format-preference) set.

### Extract archives containing issues

If an archive file has (most often multiple) complete issues inside, then extract the files inside and convert those issue files following the format preference. With the setting disabled, Kapowarr will convert the file as normal. Even when no format preference is set (= don't convert), this setting can still be enabled to extract archive files (up to beta-3, this was called 'unzipping').

_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked. If you find faulty deletions occurring, please make an issue on GitHub._

### Format Preference

The formats that Kapowarr should convert the files to. It will try to convert the files to the format at place 1, but if that is not possible, it will fall back to the format at place 2, and so forth. The last place will always be occupied by the format 'No Conversion'. That means that if Kapowarr is not able to convert the file to any of the set formats, it will just keep the current one. If no format preference is set ('No Conversion' is at place 1), no conversion will happen. 

??? info "The format called 'folder'"
	The format called 'folder' means extracting archive files containing images that directly cover a single issue. This is different from the ['Extract archives covering multiple issues' setting](#extract-archives-containing-issues). That setting will extract complete issue files from an archive file containing them. If you then add 'folder' to the format preference, it will extract any archive files coming out of the original archive file again. The format 'folder' will most likely lead to a folder with inside of it a series of image files. If you want to recreate the 'unzipping' feature from Kapowarr beta-3 and before, enable the before mentioned setting and do _not_ include 'folder' in the format preference. 

	_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked. If you find faulty deletions occurring, please make an issue on GitHub._

## Root Folders

Root folders are the base folders that Kapowarr works in. All media files are put in these folders. Kapowarr needs at least one root folder set in order to work properly.

When adding a volume (or when editing one), you choose in which root folder all content for that volume is put. You might have multiple root folders because you store your comics on multiple drives or want different access rights to certain volumes, to name a few reasons.

You can use the edit button on the right to rename a root folder. Or the delete button to remove a root folder from Kapowarr, but not actually deleting the folder on the filesystem. You can only remove a root folder when no volume in your library has their volume folder in the root folder.

!!! warning "Adding root folders on Docker"
	If you use Docker to run Kapowarr, then the root folder that you enter in the web-UI is the mapped folder, not the folder path on the host machine. That means that if you followed the [installation instructions](../installation/docker.md#launch-container), you would need to enter `/comics-1`, `/comics-2`, etc. as your root folder.
