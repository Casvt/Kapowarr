# FAQ

## Regarding the project

### Does Kapowarr support XYZ?

Look around in the web-UI and this documentation hub first, to see if you find it. Otherwise you can ask on the [Discord server](https://discord.gg/5gWtW3ekgZ). If you are sure that it is not available in Kapowarr, you can [report it](./reporting.md).

### When will XYZ be added?

First, check out the [project board](https://github.com/users/Casvt/projects/5) to see if it's already on there and if so, at what stage it is. If it's not, check if a feature request is already made for it on the [issues page](https://github.com/Casvt/Kapowarr/issues) and otherwise [make an issue yourself](./reporting.md).

## Regarding the usage

### How do I access the web-UI?

If you want to access the web-UI from the same computer that Kapowarr is running on, you can go to [http://localhost:5656](http://localhost:5656). Otherwise, you need to find out what the IP address is of the computer that Kapowarr is running on. Then you can access it via `{IP}:5656`. So if the IP address is `192.168.2.15`, you can access the web-UI via `192.168.2.15:5656` or `http://192.168.2.15:5656`.

If you can still not access the web-UI, check if the port is allowed through the firewall.

### Why do certain files pop up in the Library Import, even though I just imported them?

If you match a file with a CV volume and import it that way, but the file is not matched to the volume, the file will pop up again. So the source of the problem is that the file is not matched to any issue of the volume that it was originally matched to in the Library Import proposal. Use the ['Matching' page](../general_info/matching.md#files-to-issues) to figure out why the filename is insufficient to match to the volume.

### Why does Kapowarr not grab the links from a GC page even though they work fine?

This could have two causes: working but unsupported links, or non-matching groups.

It could be the case that the link is working, but that it's not supported by Kapowarr. For example, downloading a Mega/MediaFire folder.

Otherwise, most of the time, it's because Kapowarr does not think that the link leads to a file that actually matches the volume. Often, GC pages have multiple links, and not always are all of them relevant to the volume. Because of this, Kapowarr filters the groups and only downloads the ones that it thinks are relevant to the volume. It could be that the information does not match enough for Kapowarr to be convinced that they match. This could be because the year does not match close enough, or the title (e.g. 'ABC: Deluxe Edition' and 'The Deluxe Edition of ABC').

## Common Errors

### I can't add volumes to the library

The two most common causes for this are:

- Not having a valid [ComicVine API key](../settings/general.md#comic-vine-api-key) to be able to match or look up volumes.
- Not having a [root folder](../settings/mediamanagement.md#root-folders) defined.
