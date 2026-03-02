# Implementation Details

## Update All

The Update All task runs every hour by default. When it runs, it gathers the volumes that haven't been updated in over 24 hours. It fetches the metadata of all these volumes (not their issues). The volumes are fetched in order of their last time they were updated, so that volumes that haven't been updated the longest are first. This matters because it could be the case that not all volumes are actually fetched because the ComicVine rate limit is hit first. The rate limit allows fetching the metadata of 20.000 volumes per hour. This is why the task runs every hour even though it only updates volumes once every 24 hours: it could be that in the first run we don't actually update all volumes, so we run it again an hour later to update the remaining volumes, and so on every hour.

The received volume metadata is saved and the reported count of issues in each volume is compared to the count of issues found in the database for the volume. If they are equal, it's safe to say that nothing about the issues changed (at least there was no issue added). So the metadata of the issues of the volume aren't fetched then. If the counts aren't equal, and once every 30 days just in case, the metadata of all issues in that volume are fetched and saved.

Fetching the metadata of all volumes is relatively quick, taking between 3 and 4 minutes for 20.000 volumes (100 volumes per second). It's the fetching of all issues that can take a very long time. This is why the system that compares the issue counts to most likely skip fetching the issues is in place.

## Special Version and annuals

- **Normal Volume**  
A normal volume is a volume that has one or more issues. If the volume only has one issue, then the issue must be released within the last month. Otherwise the volume is considered a TPB by default.

- **Volume as Issue**  
A 'Volume as Issue' volume is a volume where each issue is called 'Volume N', where N is a number. Kapowarr automatically detects this by looking at the issue titles. It recognises digits (e.g. 'Volume 2') and words (e.g. 'Volume Two') but not roman numbers (e.g. NOT 'Volume III'). If you want your files to be named like a VAI (see the [File Naming For "Volume As Issue"](../settings/mediamanagement.md#file-naming-for-volume-as-issue) setting), then override the Special Version of the volume to this.

- **TPB**  
A TPB volume is a volume with only one issue: the TPB. If there is a volume that contains multiple issues where it claims that each issue is a TPB, then such a volume is a normal volume.

- **Omnibus**  
An omnibus is a volume with only one issue: the omnibus.

- **One Shot**
A one shot is a volume with only one issue: the one shot. If there is a volume that contains multiple issues where it claims that each issue is a one shot, then such a volume is a normal volume.

- **Hard Cover**
A hard cover is a volume with only one issue: the hard cover. If there is a volume that contains multiple issues where it claims that each issue is a hard cover, then such a volume is a normal volume.

If a volume is an annual, then it's a normal volume. It's not really a Special Version, but some extra checks are done based on whether the volume is an annual or not. For example, files can only match to a volume when both the volume and file are for an annual or both not. There is no setting to change whether a volume is considered an annual.

## Library Import

Files have to be in a sub-folder of the root folder in order to show up in Library Import.

If the ComicVine rate limit is reached halfway through the proposal, then unhandled files will have no match. Files that don't have a match linked to them will be ignored when importing, regardless of the state of the checkbox for that file. It's advised to wait a few minutes and then do another run.

When 'Import' is used, the volume folder that is set is the 'deepest common folder'. This is the deepest folder that still contains all files that are matched to that volume.

If you imported files but certain ones pop up again in the next run, see the [FAQ on this topic](../other_docs/faq.md#why-do-files-pop-up-in-library-import-even-though-i-just-imported-them).

## Downloading from GetComics

When a GetComics release has been chosen, either by you or by Kapowarr, Kapowarr will try to find a download link (or multiple) on the page to use for downloading the file(s). How Kapowarr decides which link(s) to use, is broken down in the following steps:

1. GetComics often offers multiple services for the same download. Kapowarr first analyses the page and collects all groups and their links (one group per download).
2. Next, it will combine multiple groups to cover as many issues as possible (if the download is for more than one issue). This collection of groups will form a 'path'. Groups are only added to a path if Kapowarr thinks that the group is actually downloading something we want. There can be multiple paths, in the case where there are conflicting groups. For example when there is a torrent download for all issues and multiple other downloads for issues 1-10, 11-20, etc.
3. All the links in the first path are tested, to see if they work, are supported and are allowed by the blocklist. A link could not be supported because the service is simply not supported, or because it's a torrent download and no torrent client is set up. If enough links pass, all the downloads in the path are added to the queue to be downloaded. If not enough links pass, the next path is tested until one is found that passes. If none pass, the page is added to the blocklist for having no working links.
4. When a path passes and its groups are added to the download queue, a decision needs to be made for which service is going to be used for each group (DDL, Mega, MediaFire, etc.). The ['Service Preference' setting](../settings/download.md#service-preference) decides this.

If Kapowarr downloads less (or nothing at all) from a page, but you are convinced that that shouldn't be the case, read about this topic [on the FAQ page](../other_docs/faq.md#why-does-kapowarr-not-grab-the-links-from-a-getcomics-page-even-though-they-work-fine).
