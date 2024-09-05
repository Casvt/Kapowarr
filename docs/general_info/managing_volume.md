# Volume Management

## Adding Volumes To Your Library

There are two ways you can add volumes - manually, or by importing.  
See the [Library Import documentation](./features.md#library-import) for more information on that.  
To add a volume to your library manually, follow the instructions below:

1. Make sure that you set a [Root Folder](../settings/mediamanagement.md#root-folders).
2. Make sure that you set your ComicVine API Key [in the settings](../settings/general.md#comic-vine-api-key).
3. In the web-UI, go to Volumes -> Add Volume.
4. Enter a search term (or the CV ID of the volume).
5. In the search results, click on the volume that you want to add.
6. Choose a root folder to put the volume folder in, set a custom volume folder (instead of the [generated one](../settings/mediamanagement.md#volume-folder-naming)) and choose if it should be monitored.
7. Click 'Add Volume' to add it to your library. Done!

## Managing Files

Now that you have a volume in your library, Kapowarr/you can start managing it.  

When clicking on a volume in your library, you get taken to the volume page. It shows information about the volume and the issues that are in it. You can also click on an issue to get extra specific information about it. At the top, there is a tool bar with multiple options.

### Refresh & Scan

The 'Refresh & Scan' button will update the metadata of the volume (= refresh) and scan for files (= scan).  
Under the metadata update falls data like the poster, title, release year and description but also the issue list and their descriptions, issue numbers and release dates.  
The file scanning will look in the volume folder for files and will try to match them to the issues. If Kapowarr is able to match them to an issue, that issue will be marked as downloaded. More information on how Kapowarr matches files to issues can be found on the ['Matching' page](./matching.md).

On the home page (a.k.a. library page/view), the button 'Update All' will trigger a Refresh & Scan for all volumes. The metadata of a volume is automatically updated every 24 hours, but will be forcibly updated if you trigger a Refresh & Scan manually. More information on the risks of doing this too often can be found on the ['Rate Limiting' page](../other_docs/rate_limiting.md#comicvine).

### Preview Rename

Kapowarr has the ability to easily manage your files by (re)naming them all to one consistent format. You can change how Kapowarr should name files and folders [in the settings](../settings/mediamanagement.md#file-naming). The 'Preview Rename' button will show a list of the files for the volume and what Kapowarr will rename them to, if you agree.

### Preview Convert

Another feature of Kapowarr is the ability to change the format of files. For example, Kapowarr can convert cbr files to cbz. To what format Kapowarr will change the files is set [in the settings](../settings/mediamanagement.md#format-preference). The 'Convert' button will show a list of the files for the volume and what format Kapowarr will convert them to, if you agree.

!!! info "Extracting Archives"
    If you download multiple issues in one go, they often come in a zip file (e.g. `Issue 1-10.zip`). Kapowarr can extract these archive files and put the contents directly in the folder. See the ['Extract archives covering multiple issues' setting](../settings/mediamanagement.md#extract-archives-covering-multiple-issues) to enable this.

### Root folder and Volume folder

Clicking on the 'Edit' button will show a screen where you can edit the two folders of the volume: the root folder and the volume folder. The root folder is the base folder that the volume folder lives in and the volume folder is the specific folder inside the root folder that is destined for the volume. You can change both, and Kapowarr will move everything to the correct location for you.

## Downloading

This section covers the 'downloading' category. Implementation details on how Kapowarr downloads media can be found on the ['Downloading' page](./downloading.md).

### Monitoring

If a volume is monitored, Kapowarr will try to automatically download media for it. If a volume is unmonitored, it won't. The monitored status does not exclude a volume from manual downloads, metadata updates ([Refresh & Scan](#refresh--scan)) or file scanning. You can also (un)monitor individual issues of a volume.

### Auto Search

The button 'Search Monitored' will make Kapowarr try to download media for issues that aren't downloaded yet. This button only does something if the volume is monitored and at least one of it's monitored issues doesn't have a file yet. It uses [GetComics](https://getcomics.org) as it's source. It will try to find a download for as many issues as possible, but it isn't guaranteed that it will always find a matching and working download.

On the home page, the button 'Search All' will trigger a 'Search Monitored' for all monitored volumes. This is done every 24 hours automatically, but you can also trigger it manually.

### Manual Search

The button 'Manual Search' will show you a list of search results for the volume/issue. From these results, you can choose yourself which one Kapowarr will download. It is possible that the page does not contain any matching and working downloads. In that case, the download button will turn red and the page will be added to the blocklist.

### Download Queue and Post Processing

When a download is added to the queue, you can see it on the Activity -> Queue page. Kapowarr will download the files one by one (except for torrent files, the queue for those is handled by the torrent client). When a download is complete, it will enter post-download processing (a.k.a. post-processing). Entirely depending on your configuration, the file could be renamed, converted to a different format and/or be extracted (if it's an archive file with multiple issues inside). It will always be moved from the [download folder](../settings/download.md#direct-download-temporary-folder) to it's final destination inside the volume folder.

When you view the volume after the download, you'll see that the issue now has a check mark on the right, indicating that it has been downloaded.
