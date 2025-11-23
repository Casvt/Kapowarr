# Indexers

Kapowarr supports searching for comics using usenet and torrent indexers through the Newznab and Torznab APIs. You can add indexers manually or sync them from Prowlarr.

## What are Indexers?

Indexers are services that index content from usenet newsgroups or torrent trackers, making it searchable. Popular comic indexers include:

- **Usenet Indexers** (Newznab): DrunkenSlug, AlTHub, NZBgeek, etc.
- **Torrent Indexers** (Torznab): Various private and public trackers

When you perform a manual or automatic search in Kapowarr, it will search all enabled indexers in addition to GetComics.

## Adding Indexers

### Manual Configuration

To manually add an indexer:

1. Go to **Settings** → **Indexers**
2. Click **Add Indexer**
3. Fill in the required information:
   - **Name**: A friendly name for the indexer (e.g., "DrunkenSlug")
   - **Base URL**: The indexer's API URL (e.g., `https://api.drunkenslug.com`)
   - **API Key**: Your personal API key from the indexer
   - **Type**: Select `Newznab` for usenet or `Torznab` for torrents
   - **Categories**: Comic category ID (default: `7030` for comics)
4. Click **Save**

### Using Prowlarr

[Prowlarr](https://prowlarr.com/) is an indexer manager that can sync your indexers to Kapowarr automatically.

To use Prowlarr:

1. Install and configure Prowlarr with your indexers
2. In Kapowarr, go to **Settings** → **Prowlarr**
3. Enter your Prowlarr details:
   - **Base URL**: Your Prowlarr instance URL (e.g., `http://localhost:9696`)
   - **API Key**: Your Prowlarr API key (found in Prowlarr Settings → General)
4. Click **Test** to verify the connection
5. Click **Sync Indexers** to import all comic-capable indexers from Prowlarr

Prowlarr will automatically filter for indexers that support comic categories.

## Managing Indexers

### Enable/Disable Indexers

You can temporarily disable an indexer without deleting it:

1. Go to **Settings** → **Indexers**
2. Find the indexer in the list
3. Toggle the **Enabled** switch

Only enabled indexers are searched during manual and automatic searches.

### Editing Indexers

To edit an existing indexer:

1. Go to **Settings** → **Indexers**
2. Click on the indexer you want to edit
3. Update the fields as needed
4. Click **Save**

### Deleting Indexers

To remove an indexer:

1. Go to **Settings** → **Indexers**
2. Click on the indexer you want to remove
3. Click **Delete**
4. Confirm the deletion

## How Indexers Work with Searches

When you perform a search (manual or automatic), Kapowarr will:

1. Search GetComics (web scraping)
2. Search all enabled indexers in parallel
3. Combine and deduplicate results
4. Rank results based on relevance

The indexer results will appear alongside GetComics results in the search interface, labeled with the indexer name as the source.

## Download Clients

To download content found through indexers, you need to configure appropriate download clients:

- **For Usenet**: Configure a [SABnzbd client](./downloadclients.md#sabnzbd) in Settings → Download Clients
- **For Torrents**: Configure a [torrent client](./downloadclients.md#torrent-clients) (qBittorrent, Transmission, etc.)

Kapowarr will automatically send downloads to the appropriate client based on the source type.

## Categories

The default category `7030` corresponds to comics in the Newznab/Torznab category structure:

- `7000` - Books (root category)
- `7010` - Magazines
- `7020` - Ebook
- `7030` - **Comics**

Most indexers use this standard, but some may have different category IDs. Check your indexer's documentation if needed.

## Troubleshooting

### Indexer not returning results

- Verify your API key is correct
- Check that the indexer supports the comic category (`7030`)
- Ensure the indexer is enabled in Kapowarr
- Check the indexer's website to confirm it's operational

### Prowlarr sync not working

- Verify Prowlarr is running and accessible
- Check that the API key is correct
- Ensure Prowlarr has indexers configured with comic support
- Check Kapowarr logs for detailed error messages

### Downloads not starting

- Ensure you have configured the appropriate download client (SABnzbd for usenet, torrent client for torrents)
- Check that the download client is running and accessible
- Verify the download client credentials are correct
