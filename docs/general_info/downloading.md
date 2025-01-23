# Downloading

When a GetComics (GC) release has been chosen, either by you or by Kapowarr, Kapowarr will try to find a download link (or multiple) on the page to use for downloading the file(s). How Kapowarr decides which link(s) to use, is broken down in the following steps:

1. GC often offers multiple services for the same download. Kapowarr first analyses the page and collects all groups and their links (one group per download).
2. Next, it will combine multiple groups to cover as many issues as possible (if the download is for more than one issue). This collection of groups will form a 'path'. Groups are only added to a path if Kapowarr thinks that the group is actually downloading something we want. There can be multiple paths, in the case where there are conflicting groups. For example when there is a torrent download for all issues and multiple other downloads for issues 1-10, 11-20, etc.
3. All the links in the first path are tested, to see if they work, are supported and are allowed by the blocklist. A link could not be supported because the service is simply not supported, or because it's a torrent download and no torrent client is set up. If enough links pass, all the downloads in the path are added to the queue to be downloaded. If not enough links pass, the next path is tested until one is found that passes. If none pass, the page is added to the blocklist for having no working links.
4. When a path passes and it's groups are added to the download queue, a decision needs to be made for which service is going to be used for each group (direct download, Mega, MediaFire, etc.). The ['Service Preference' setting](../settings/download.md#service-preference) decides this.

If Kapowarr downloads less (or nothing at all) from a page, but you are convinced that that shouldn't be the case, read about this topic [on the FAQ page](../other_docs/faq.md#why-does-kapowarr-not-grab-the-links-from-a-gc-page-even-though-they-work-fine).
