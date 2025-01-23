This page covers how Kapowarr matches certain things. First a note on the Special Version, as it affects all matching.

!!! tip "Matching using year"
	If it is an option to match using the year, both the release year of the volume and the release year of the issue is allowed. The year is also allowed to be off by one from the reference year.

## Special Version

The matching criteria differ based on the type of volume. Kapowarr calls this the "Special Version" of the volume. A volume can be a "Normal Volume", "Trade Paper Back", "One Shot", "Hard Cover" or "Volume As Issue". Kapowarr tries it's best to automatically determine the type, but there are scenario's where it's wrong. You can override the Special Version when adding a volume, or by editing the volume. This setting is one of the first things you should check in case matching does not work for a volume.

!!! info "What is a "Volume As Issue" volume?"
	The "Volume As Issue" Special Version is for volumes where each issue is named "Volume N", where N is a number. An example of such a volume is [Reign of X](https://comicvine.gamespot.com/reign-of-x/4050-137265/). Issue 1 is named "Volume 1", issue 2 is named "Volume 2", etc.

If a specific string is required, most common variations are also supported. For example, if the string 'one-shot' is required, the variations 'one shot' and 'os' are also allowed. And upper case or lower case does not matter. 

## Files to Issues

This covers how Kapowarr matches files to issues of a volume. Information is extracted from the filename, folder and parent folder.

### Normal Volume

Rules:

1. Has to mention issue number and should match.
2. Either year or volume number has to be mentioned and should match.

Examples:

1. `Iron-Man Volume 2 Issue 3.cbr`
2. `Batman (1940) Vol. 2 #11-25.zip`

### 'Volume As Issue' Volume

This is a volume where the issue titles are in the format 'Volume N'.

Rules:

1. Volume number of file refers to issue number of volume or volume number of file refers to volume number of volume and issue number of file refers to issue number of volume.
2. Either year or volume number has to be mentioned and should match.

Examples:

1. `Invincible Compendium (2011) Volume 2 - 3.cbr`
2. `Invincible Compendium (2011) Volume 1 Issue 2 - 3.cbr`

### TPB Volume

Rules:

1. Is allowed to have 'TPB'.
2. Is not allowed to have issue number.
3. Either year or volume number has to be mentioned and should match.

Examples:

1. `Silver Surfer Rebirth (2022) Volume 1 TPB.cbz`
2. `Silver Surfer Rebirth (2022) Volume 1.cbz`
3. `Silver Surfer Rebirth Volume 1.cbz`
4. `Silver Surfer Rebirth (2022).cbz`

The following is _not_ allowed:

1. `Silver Surfer Rebirth Volume 1 Issue 001.cbz`

### One Shot Volume

Rules:

1. Has to mention 'one-shot', issue number 1 or no issue number.
2. Either year or volume number has to be mentioned and should match.

Examples:

1. `Elvira Mistress of the Dark Spring Special One Shot (2019) Volume 1.cbz`
2. `Elvira Mistress of the Dark Spring Special (2019).cbz`
3. `Elvira Mistress of the Dark Spring Special Volume 1.cbz`
4. `Elvira Mistress of the Dark Spring Special Volume 1 Issue 001.cbz`

### Hard Cover Volume

Rules:

1. Has to mention 'hard-cover', issue number 1 or no issue number.
2. Either year or volume number has to be mentioned and should match.

Examples:

1. `John Constantine, Hellblazer 30th Anniversary Celebration (2018) Hard-Cover.cbr`
2. `John Constantine, Hellblazer 30th Anniversary Celebration (2018).cbr`
3. `John Constantine, Hellblazer 30th Anniversary Celebration Volume 1.cbr`
4. `John Constantine, Hellblazer 30th Anniversary Celebration Volume 1 Issue 01.cbr`

## GetComics Search Results

When searching for a GC release, Kapowarr determines if the page is a match for the volume or not. The release has to conform with the following rules to pass the filter:

1. Not be blocklisted.
2. Series title has to match.
3. If the volume number is given, it should match.
4. If the year is given, it should match.
5. If it is for a hard cover or one shot, it has to follow the first rule they have for files.
6. If it is for a TPB, it has to follow the first two rules it has for files.
7. If not a special version, the issue number should match to an issue in the volume.

## GetComics Groups

When selecting links from a GC page for downloading, Kapowarr filters the groups so that no irrelevant files are downloaded. See the ['Downloading' page](./downloading.md) for more information. The download group has to conform with the following rules to pass the filter:

1. Series title has to match.
2. If the volume number is given, it should match.
3. If the year is given, it should match.
4. If it is for a hard cover or one shot, it has to follow the first rule they have for files.
5. If it is for a TPB, it has to follow the first two rules it has for files.

## Archive Extractions

When extracting files from archives, the files are filtered and deleted if they are not for the volume. A file has to conform with the following rules to pass the filter:

1. Series title has to match.
2. Either year or volume number has to be mentioned and should match, or neither should be mentioned.
