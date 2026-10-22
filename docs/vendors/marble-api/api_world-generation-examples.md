> ## Documentation Index
> Fetch the complete documentation index at: https://docs.worldlabs.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# World generation examples

> Example-based request patterns for generating worlds from text, images, panoramas, multiple images, and video.

Use these examples when you already know the kind of input you want to send.
For the full request schema, see [`POST /marble/v1/worlds:generate`](/api/reference/worlds/generate).

## Text prompt

Text prompts are the smallest request. The API generates the panorama first,
then generates the world from that panorama.

```bash theme={null}
curl -X POST 'https://api.worldlabs.ai/marble/v1/worlds:generate' \
  -H 'Content-Type: application/json' \
  -H 'WLT-Api-Key: YOUR_API_KEY' \
  -d '{
    "display_name": "Sunlit Atrium",
    "model": "marble-1.1",
    "world_prompt": {
      "type": "text",
      "text_prompt": "A sunlit indoor atrium with marble floors, plants, and tall glass windows"
    }
  }'
```

## Single image

For a regular photo or illustration, omit `is_pano` or set it to `false`.
The API uses the image to generate a panorama, then generates the world.

```bash theme={null}
curl -X POST 'https://api.worldlabs.ai/marble/v1/worlds:generate' \
  -H 'Content-Type: application/json' \
  -H 'WLT-Api-Key: YOUR_API_KEY' \
  -d '{
    "display_name": "Greenhouse Workshop",
    "model": "marble-1.1",
    "world_prompt": {
      "type": "image",
      "image_prompt": {
        "source": "uri",
        "uri": "https://example.com/greenhouse.jpg"
      },
      "text_prompt": "A peaceful greenhouse workshop with warm light and dense plants"
    }
  }'
```

<Note>
  A `source: "uri"` URL must be fetchable by World Labs servers with no cookies,
  authentication, or referer. Hotlink-protected or login-gated hosts can block
  these fetches and return a `400`. If a URL won't fetch, upload the file as a
  media asset or inline it with `source: "data_base64"`. See
  [Errors and troubleshooting](/api/errors).
</Note>

## Existing panorama

If your image is a full 360-degree equirectangular panorama, send it as an
image prompt. `is_pano` defaults to `auto`, so the API checks whether the image
looks like a valid equirectangular panorama before skipping pano generation.

```bash theme={null}
curl -X POST 'https://api.worldlabs.ai/marble/v1/worlds:generate' \
  -H 'Content-Type: application/json' \
  -H 'WLT-Api-Key: YOUR_API_KEY' \
  -d '{
    "display_name": "Captured Apartment Pano",
    "model": "marble-1.1",
    "world_prompt": {
      "type": "image",
      "image_prompt": {
        "source": "uri",
        "uri": "https://example.com/apartment-equirect-pano.jpg"
      },
      "is_pano": "auto"
    }
  }'
```

Set `is_pano` to `true` when your integration has already validated the image
as a pano. Set it to `false` for wide 2:1 images that are not 360-degree
equirectangular panoramas, such as banners, crops, or collages.

## Multiple images

Use multi-image input when you have several views of the same scene. Add
`azimuth` values when you know where each image faces.

```bash theme={null}
curl -X POST 'https://api.worldlabs.ai/marble/v1/worlds:generate' \
  -H 'Content-Type: application/json' \
  -H 'WLT-Api-Key: YOUR_API_KEY' \
  -d '{
    "display_name": "Living Room From Two Views",
    "model": "marble-1.1",
    "world_prompt": {
      "type": "multi-image",
      "multi_image_prompt": [
        {
          "azimuth": 0,
          "content": {
            "source": "uri",
            "uri": "https://example.com/living-room-front.jpg"
          }
        },
        {
          "azimuth": 180,
          "content": {
            "source": "uri",
            "uri": "https://example.com/living-room-back.jpg"
          }
        }
      ],
      "text_prompt": "A cozy living room with a fireplace and bookshelves"
    }
  }'
```

## Local media

For local files, create a media asset, upload to the signed URL, then reference
the returned `media_asset_id` in `world_prompt`. The same flow works for local
images, local panoramas, and local videos.

```json theme={null}
{
  "display_name": "Uploaded Pano",
  "model": "marble-1.1",
  "world_prompt": {
    "type": "image",
    "image_prompt": {
      "source": "media_asset",
      "media_asset_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "is_pano": "auto"
  }
}
```

See the [Quickstart upload flow](/api#image-input) for the signed upload steps.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.