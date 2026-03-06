# How To Use

This is a guide to using Kapowarr, after installation and setup.

## Adding Volumes To Your Library

There are two ways you can add volumes: manually or by importing existing media files for the volume. To add a volume by importing existing media files for it, see the [Library Import documentation](./library_import.md). To manually add a volume:

1. In the web-UI, go to Volumes -> Add Volume.
2. Enter a search term (or the ComicVine ID of the volume).
3. In the search results, click on the volume that you want to add.
4. Choose a root folder to put the volume folder in and whether it should be monitored. For an explanation of all the options, see the ['Editing a volume' section below](#editing-a-volume).
5. Optionally enable immediately downloading missing issues once the volume is added by checking the checkbox next to the 'Add Volume' button.
5. Click 'Add Volume' to add it to your library. Done!

## Managing the volume

Once you have added volumes to your library, you can click on one to view it. Here you can manage your volume.

### Refresh & Scan

In the bar at the top, the 'Refresh & Scan' button will update the metadata of the volume (= 'refresh') and scan for files (= 'scan'). Updating the metadata means reaching out to ComicVine and getting a fresh version of the poster, title, release year and description but also (and more importantly) the list of issues and their descriptions, issue numbers and release dates. Scanning for files means looking in the volume folder (the folder linked to the volume) for media files and matching them to the issues. If Kapowarr is able to match them to an issue, that issue will be marked as downloaded. The file has to pass a list of [criteria](./matching.md#files-to-issues) in order to match to an issue.

On the home page (a.k.a. the library page), the button 'Update All' will trigger a Refresh & Scan for all volumes. It automatically runs, but how often it automatically updates a volume is a bit complicated. See the [implementation details](./implementation_details.md#update-all) for more information. But in general you can trust that volumes stay up-to-date with a few hours of margin.

### Monitoring

If a volume is monitored, it means that Kapowarr will automatically try to download files for its issues. You can monitor and unmonitor volumes by clicking the flag next to their title, by editing the volume and by clicking the flag when viewing the table on the library page. You can also monitor and unmonitor individual issues of a volume by clicking on the flags in the issue table. Whether an issue is monitored or not becomes irrelevant once the entire volume is unmonitored. The monitored status does not exclude a volume from manual downloads, metadata updates (Refresh & Scan) or file scanning.

### Editing a volume

You can edit some properties of the volume by clicking on the 'Edit' button.

- **Monitor Volume**  
Whether or not to monitor the volume.

- **Monitor New Issues**  
Whether or not newly released issues should be monitored or not by default. You can always manually change the monitored status of an issue later by clicking on the flag icon.

- **Monitoring Scheme**  
Applying a monitoring scheme is an action that can be performed, rather than a property of the volume. The selected monitoring scheme is applied once, on save. You can apply any monitoring scheme you want, however often you want. A monitoring scheme is a logical rule behind whether an existing issue should become monitored or not. The monitoring scheme 'All' will simply monitor all issues in the volume. The monitoring scheme 'Missing' will only monitor issues that are not marked as downloaded. The monitoring scheme 'None' will unmonitor all issues in the volume. This only applies to the existing issues in the volume. For new issues, see the 'Monitor New Issues' option above. Leave the value at 'Don't apply' to not apply any monitoring scheme.

- **Root Folder**  
The root folder that the volume folder is in. If you change the root folder and click 'Update', then the new folder is created, all files matched to the volume are moved into the new folder and the old one is deleted (if empty).

- **Volume Folder**  
The relative path from the root folder to the volume folder. This path is automatically generated based on the ['Volume Folder Naming' setting](../settings/mediamanagement.md#volume-folder-naming). If you change the value and click 'Update', then the new folder is created, all files matched to the volume are moved into the new folder and the old one is deleted (if empty). You can empty the field and click 'Update' to generate the default path based on the mentioned setting.

- **Special Version**  
Override the Special Version of the volume, or allow Kapowarr to automatically determine it. If the value is changed from being overridden to 'Automatic', then the Special Version is evaluated the next time a Refresh & Scan (or Update All) is ran. See the section below for an explanation of the Special Version.

### Special Version

The 'Special Version' of a volume is what Kapowarr calls the 'type' of comic. A comic can for example just be a normal one with issues ('Normal Volume'), but it could also be a 'Trade Paper Back', 'One Shot', 'Hard Cover', 'Omnibus' or 'Volume as Issue'. It's _very_ important that the determined type is correct for the volume, as it influences everything from matching files to issues, to validating downloads, to naming of the files. The Special Version of the volume is shown in the yellow box just below the volume title. Kapowarr automatically tries to determine what the Special Version of the volume is, but it can sometimes be wrong. You can override the Special Version of a volume by editing it, or in the popup window when adding one. For details on what the correct Special Version of a volume should be, see the [implementation details](./implementation_details.md#special-version-and-annuals).

!!! info "What is a "Volume As Issue" volume?"
	The "Volume As Issue" Special Version is for volumes where each issue is named "Volume N", where N is a number. An example of such a volume is [Reign of X](https://comicvine.gamespot.com/reign-of-x/4050-137265/). Issue 1 is named "Volume 1", issue 2 is named "Volume 2", etc.

!!! warning "Check the Special Version in case of problems"
    If you're having problems with a volume, the very first thing to check is whether the Special Version is correct. As mentioned, it influences a lot of behaviour.

## Managing the files

Now that we know how to manage the volume itself, let's look at how to manage the media files.

### General Files

General files are files that are for the volume, but not a specific issue. Examples of such files are volume metadata files and volume cover files. You can see the general files matched to the volume by clicking on the 'General Files' button at the top. 

### Manage Issues

You can change how files in the volume folder match to the volume. By clicking on the 'Manage Issues' button, a window opens with a list of all files in the volume folder and what they are matched to. The files could be matched to one or more issues, be matched to the volume as a general file, or not be matched to anything. Using the checkboxes on the left, you can select one or more files and then click the 'Set Match' button to change what they match to. On the new window, select whether the file should just automatically be matched (standard behaviour), or be forcibly matched to the volume as a general file or to one or more issues. Click 'Select' to save the (new) match. If the file was previously forcibly matched and is now selected to be automatically matched, the 'Matched To' column will say 'TBD' ('To Be Determined') as it's unknown at that point in time what the file will match to. Click 'Save' once you're done changing the matches and Kapowarr will apply the new matches and do a standard file scan (like when a Refresh & Scan is run) to match the files that are marked to automatically match.

### Preview Rename

Kapowarr has the ability to easily manage your files by (re)naming them all to one consistent format. You can change how Kapowarr should name files and folders [in the settings](../settings/mediamanagement.md#file-naming). The 'Preview Rename' button will show a list of the media files matched to the volume and what they will be renamed to. Click the 'Rename' button to finalise it.

### Preview Convert

Another feature of Kapowarr is the ability to change the format of files. For example, Kapowarr can convert cbr files to cbz. To what format Kapowarr will (try to) change the files is set [in the settings](../settings/mediamanagement.md#format-preference). The 'Preview Convert' button will show a list of the media files matched to the volume and what format they will be converted to. Click the 'Convert' button to finalise it.

!!! info "Extracting Archives"
    If you download multiple issues in one go, they often come in an archive file (e.g. `Issue 1-10.zip`). Kapowarr can extract these archive files and put the contents directly in the folder. This functionality falls under 'Conversion'. See the ['Extract archives containing issues' setting](../settings/mediamanagement.md#extract-archives-containing-issues) to enable this.

## Downloading

This section covers searching for, and downloading, files for issues.

### Search Monitored

The button 'Search Monitored' will make Kapowarr try to download media files for issues that aren't downloaded yet. This button only does something if the volume is monitored and at least one of its monitored issues doesn't have a file yet. It will try to find a download for as many issues as possible, but it isn't guaranteed that it will always find a matching and working download.

On the library page, the button 'Search All' will trigger a 'Search Monitored' for all monitored volumes. A search is done automatically every 24 hours by default, but you can also trigger it manually.

### Manual Search

The button 'Manual Search' will show you a list of search results for the volume/issue. From these results, you can choose yourself which one should be downloaded (instead of Kapowarr automatically choosing with Search Monitored). It is possible that the search result does not contain any matching and working downloads. In that case, the download button will turn red and the page will be added to the blocklist. Hover with your mouse over the red button to see the reason why it failed. If Kapowarr is convinced that the download links [don't match](./matching.md#search-results-for-downloads) to the volume but you click the download button anyway, it'll probably fail (because nothing matches). If you still want Kapowarr to download it, then click the icon next to the download icon, which will _force_ download it.

### Download Queue and Post Processing

When a download is added to the queue, you can see it on the Activity -> Queue page. When a download is complete, it will enter post-download processing (a.k.a. post-processing). Entirely depending on your configuration, the file could be renamed, converted to a different format and/or be extracted (if it's an archive file with issues inside). It will always be moved from the [download folder](../settings/download.md#direct-download-temporary-folder) to its final destination inside the volume folder.

When you view the volume after the download, you'll see that the issue now has a check mark on the right, indicating that it has been downloaded.
