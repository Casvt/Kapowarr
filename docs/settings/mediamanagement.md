## Media Management

Here is where you configure your settings related to how your media files are handled.

### File Naming

#### Rename Downloaded Files
When a file is downloaded, this setting decides if it should be renamed or not. If not, the default filename is used. If so, it is renamed following the formats set below.

#### Volume Folder Naming

The naming format for the volume folder (folder structure allowed).  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}

For example, `{series_name} ({year})` will come out as "Invincible Iron Man (2019)".

#### File Naming

The naming format for the file itself.  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}
- {issue_comicvine_id}
- {issue_number}
- {issue_title}
- {issue_release_date}
- {issue_release_year}

For example, `{series_name} ({year}) Volume {volume_number} Issue {issue_number} {issue_title}` would come out as "Invincible Iron Man (2008) Volume 01 Issue 001 The Five Nightmares Part 1 Armageddon Days.cbz".

#### File Naming For TPB

The naming format for the file itself (if it's a TPB).  
Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}

For example, `{series_name} ({year}) Volume {volume_number} TPB` would come out as "Invincible Iron Man (2019) Volume 01 TPB.cbz"

#### File Naming For Issues Without Title

The naming format for the file itself if there is no issue-specific title.

If the value of the setting [File Naming](#file-naming-1) uses the issue title, it will most likely look ugly when the issue doesn't have a title. For example, if your format is `Issue {issue_number} - {issue_title}`, but the issue doesn't have a title, it will result in a file like `Issue 5 - .cbr`. For that scenario, this setting exists. Here you can set an alternative format for when the issue doesn't have a title.

Available variables are:

- {series_name}
- {clean_series_name}
- {volume_number}
- {comicvine_id}
- {year}
- {publisher}
- {issue_comicvine_id}
- {issue_number}
- {issue_release_date}
- {issue_release_year}

For example, `{series_name} ({year}) Volume {volume_number} Issue {issue_number}` would come out as "Invincible Iron Man (2008) Volume 01 Issue 001.cbz".

#### Treat Volume Issues as "No Title"

Sometimes a volume will consist of multiple sub-volumes. This setting controls whether Kapowarr should name these the same as issues without a title or not. See the example below:

| Setting | Example Result |
| ------- | -------------- |
| Enabled | Invincible Compendium (2011) Volume 1 Issue 1-2.cbr<br>Invincible Compendium (2011) Volume 1 Issue 3.cbr |
| Disabled | Invincible Compendium (2011) Volume 1 - 2.cbr<br>Invincible Compendium (2011) Volume 3.cbr |

#### Issue Padding

This defines how issue numbers are 'padded' (3 digits, 2 digits, etc.).  
This is useful in the case of file sorting, as many operating systems sort _alphabetically_, instead of alphanumerically. To them, because 1 is lower than 2, "11" comes before "20".  
To get around this, we 'pad' the numbers with leading zeroes. "1" becomes"001", "11" becomes "011", and "2" becomes "002" - resulting in a more accurate sort.

Options are:

- x (no padding, i.e. 1,2,...10)
- 0x (2 digits, i.e. 01, 02...10)
- 00x (3 digits, i.e. 001, 002...010...099,100)

#### Volume Padding

This defines how volume numbers are 'padded' (3 digits, 2 digits, etc.).  
This is useful in the case of file sorting, as many operating systems sort _alphabetically_, instead of alphanumerically. To them, because 1 is lower than 2, "11" comes before "20".  
To get around this, we 'pad' the numbers with leading zeroes. "1" becomes"001", "11" becomes "011", and "2" becomes "002" - resulting in a more accurate sort.

Options are:

- x (no padding, i.e. 1,2,...10)
- 0x (2 digits, i.e. 01, 02...10)
- 00x (3 digits, i.e. 001, 002...,010...099,100)

### Converting

The "Converting" feature allows you to change the format of your files (e.g. from cbr to cbz). It can also extract archive files.

#### Covert Files

If Kapowarr should automatically convert files after they've been downloaded. Kapowarr will follow the format preference set.

#### Extract archives covering multiple issues

If an archive file is downloaded with multiple issues inside, then first extract the files inside and _then_ convert. With the setting disabled, Kapowarr will covert the file as normal. Even when no format preference is set (don't convert), this setting can still be enabled to extract archive files (up to beta-3, this was called 'unzipping').

#### Format Preference

The formats that Kapowarr should convert the files to. It will try to convert the files to the format at place 1, but if that is not possible, it will fallback to the format at place 2, and so forth. The last place will always be occupied by the format 'No Conversion'. That means that if Kapowarr is not able to convert the file to any of the set formats, it will just keep the current one. If no format preference is set ('No Conversion' is at place 1), no conversion will happen. The format 'folder' means extracting archive files. Kapowarr will extract all files inside the archive, delete the original archive file, filter unrelated files and rename the relevant ones.

_Note: if Kapowarr determines that a file in the archive file is not related to the volume, it will not be extracted and will be deleted when the archive file is finished being unpacked.
If you find faulty deletions occurring, please [lodge an issue](https://github.com/Casvt/Kapowarr/issues) for this._

### Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders.  

When adding a volume (or when editing one), you choose in which root folder all content for that volume is put. Kapowarr will never touch any files outside the root folders (except in the [download folder](#download-location)). You might have multiple root folders because you store your comics on multiple drives or want different access rights to certain volumes, to name a few reasons.

Root folders can be added at Settings -> Media Management -> Root Folders. Note: If you use docker to run Kapowarr and have followed the example given in the [installation instructions](../installation/docker.md), this is where you would enter `/comics-1`, `/comics-2`, `/RF`, `/RF2`, etc.

_Note: at least one of these must be set before you are able to add any volumes to monitor, as without it Kapowarr cannot know where to put the files._
