# GPT DownloadThat Multilingual Creator Kit

This extension renders the DownloadThat influencer recruitment and promotion kit in the eight priority languages already used by the project workflow:

- German (`de`)
- English (`en`)
- French (`fr`)
- Spanish (`es`)
- Italian (`it`)
- Arabic (`ar`, RTL)
- Japanese (`ja`)
- Chinese (`zh`)

Each language bundle contains:

- 1080×1920 Story
- 1080×1350 Feed creative
- 1280×720 YouTube thumbnail
- 1080×1350 personalised creator/QR card
- A4 recruitment flyer as PNG and PDF
- localised copy pack
- 12-second H.264/AAC creator reel
- matching SRT subtitles

## Render all languages

```bash
uv run --project gpt_downloadthat_creator_kit/gpt_multilingual/gpt_creator_tools \
  python gpt_downloadthat_creator_kit/gpt_multilingual/gpt_creator_tools/gpt_generate_multilingual_repo.py \
  --config gpt_downloadthat_creator_kit/gpt_multilingual/gpt_creator_tools/gpt_config.json \
  --out gpt_downloadthat_creator_kit/gpt_multilingual/gpt_outputs
```

## Render selected languages

```bash
uv run --project gpt_downloadthat_creator_kit/gpt_multilingual/gpt_creator_tools \
  python gpt_downloadthat_creator_kit/gpt_multilingual/gpt_creator_tools/gpt_generate_multilingual_repo.py \
  --languages en fr ar ja
```

## Personalisation

Edit `gpt_creator_tools/gpt_config.json`:

- `creator_name`
- `creator_handle`
- `affiliate_code`
- `affiliate_link`
- `contact_name`
- `contact_email`
- `languages`

## Translation quality

The eight language packs are complete AI-assisted marketing translations. Before a paid campaign, a native speaker should review the final copy, especially legal disclosures and idiomatic hooks. Product facts and financial terms remain derived from the repository's current affiliate documentation.
