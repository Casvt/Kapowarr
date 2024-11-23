In the 'Media Management' sub-section, you can find settings related to the placement, naming and format of files.

## File Naming

### Rename Downloaded Files

When a file is downloaded, this setting decides if it should be renamed or not. If the checkbox is unchecked, the default filename is used. If the checkbox is checked, it is renamed following the formats set below. This does not affect the naming of the volume folder, only the filename itself.

| Setting | Example Result |
| ------- | -------------- |
| Disabled | Deadpool 01 (of 04) (1994) (digital) (Minutemen-Slayer).cbr |
| Enabled | Deadpool (1994) Volume 02 Issue 001.cbr |

### Volume Folder Naming

The naming format for the volume folder. Keep in mind that the resulting name could differ slightly from the format, in the case that certain values of variables contain illegal characters. For example, if the `{series_name}` is "What If...", the resulting name will have "What If" as it's value, because the character `.` is not allowed at the end of the name in Windows. This also applies to the other naming formats in this section.

??? info "Available Variables"
	| Variable | Example Value |
	| -------- | ------------- |
	| {series_name} | The Incredibles |
	| {clean_series_name} | Incredibles, The |
	| {volume_number} | 01 |
	| {comicvine_id} | 2127 |
	| {year} | 1994 |
	| {publisher} | DC Comics |

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

The naming format for the file itself (if it's a special version, like a one shot, tpb or hard cover).

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

Whether or not to use, for example, 'One-Shot' instead of 'OS' [in the filename of special versions](#file-naming-for-special-versions). The term 'TPB' will always stay 'TPB'.

### Issue Padding

This defines how issue numbers are 'padded' (3 digits, 2 digits, etc.). This is useful in the case of file sorting, as many operating systems sort _alphabetically_, instead of alphanumerically. To them, because 1 is lower than 2, "10" comes before "2". To get around this, we 'pad' the numbers with leading zeroes.

Options are:

- x (no padding, i.e. 1, 2...99, 100)
- 0x (2 digits, i.e. 01, 02...99, 100)
- 00x (3 digits, i.e. 001, 002...099, 100)
- 000x (4 digits, i.e. 0001, 0002...0099, 0100)

### Volume Padding

This defines how volume numbers are 'padded' (3 digits, 2 digits, etc.). It has the same use case that [Issue Padding](#issue-padding) has.

Options are:

- x (no padding, i.e. 1, 2...99, 100)
- 0x (2 digits, i.e. 01, 02...99, 100)
- 00x (3 digits, i.e. 001, 002...099, 100)

## Converting

The "Converting" feature allows you to change the format of your files (e.g. from cbr to cbz). It can also extract archive files.

### Convert Downloaded Files

If Kapowarr should automatically convert files after they've been downloaded. Kapowarr will follow the [format preference](#format-preference) set.

### Extract archives covering multiple issues

If an archive file is downloaded with multiple issues inside, then first extract the files inside and _then_ convert. With the setting disabled, Kapowarr will covert the file as normal. Even when no format preference is set (don't convert), this setting can still be enabled to extract archive files (up to beta-3, this was called 'unzipping').

_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked. If you find faulty deletions occurring, please [report](../other_docs/reporting.md) this._

### Format Preference

The formats that Kapowarr should convert the files to. It will try to convert the files to the format at place 1, but if that is not possible, it will fall back to the format at place 2, and so forth. The last place will always be occupied by the format 'No Conversion'. That means that if Kapowarr is not able to convert the file to any of the set formats, it will just keep the current one. If no format preference is set ('No Conversion' is at place 1), no conversion will happen. 

??? info "The format called 'folder'"
	The format called 'folder' means extracting archive files. Kapowarr will extract all files inside the archive, delete the original archive file, filter unrelated files and rename the relevant ones. This is different from the ['Extract archives covering multiple issues' setting](#extract-archives-covering-multiple-issues). That setting will extract the files from an archive file covering multiple issues and will then convert those extracted files. If you then add 'folder' to the format preference, it will extract any archive files coming out of the original archive file again. The format 'folder' will most likely lead to a folder with inside of it a series of image files. If you want to recreate the 'unzipping' feature from Kapowarr beta-3 and before, enable the before mentioned setting and do _not_ include 'folder' in the format preference. 

	_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked. If you find faulty deletions occurring, please [report](../other_docs/reporting.md) this._

## Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders. Kapowarr needs at least one root folder set in order to work properly.

When adding a volume (or when editing one), you choose in which root folder all content for that volume is put. Kapowarr will never touch any files outside the root folders (except in the [download folder](#download-location)). You might have multiple root folders because you store your comics on multiple drives or want different access rights to certain volumes, to name a few reasons.

!!! warning Adding root folders on Docker
	If you use Docker to run Kapowarr, then the root folder that you enter in the web-UI is the mapped folder, not the folder path on the host machine. That means that if you followed the [installation instructions](../installation/docker.md#launch-container), you would need to enter `/comics-1`, `/comics-2`, etc. as your root folder.
