# Create read URL

POST /api/v2/assets/{asset}:createReadUrl

Mint a signed read URL for an asset



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/assets/asset_01jexample000000000000000:createReadUrl' \
  --header "WLT-Api-Key: $WLT_API_KEY"
```


## Response

```json
{
  "readUrl": "https://example.com/image.png",
  "expiresAt": "2026-09-14T20:00:00Z"
}
```



## OpenAPI specification

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Marble 2 Developer API",
    "summary": "External Developer API for Marble 2.",
    "description": "Developer API routes authenticate with a project API key and operate on that key's account and project.",
    "version": "2.0.0"
  },
  "paths": {
    "/api/v2/assets/{asset}:createReadUrl": {
      "post": {
        "tags": [
          "assets"
        ],
        "summary": "Mint a signed read URL for an asset",
        "operationId": "create_read_url_api_v2_assets__asset__createReadUrl_post",
        "parameters": [
          {
            "name": "asset",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Asset"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/CreateReadUrlResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        },
        "x-marble-authorization": {
          "permission": "asset.read"
        }
      }
    }
  },
  "components": {
    "schemas": {
      "CreateReadUrlResponse": {
        "properties": {
          "readUrl": {
            "type": "string",
            "title": "Readurl",
            "description": "Short-lived download URL for the asset's bytes. Anyone with the URL can read the asset until it expires; create a fresh one rather than persisting this."
          },
          "expiresAt": {
            "type": "string",
            "format": "date-time",
            "title": "Expiresat",
            "description": "When ``readUrl`` stops authorizing the download."
          }
        },
        "type": "object",
        "required": [
          "readUrl",
          "expiresAt"
        ],
        "title": "CreateReadUrlResponse",
        "description": "A short-lived credential for downloading one asset."
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          },
          "input": {
            "title": "Input"
          },
          "ctx": {
            "type": "object",
            "title": "Context"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      }
    },
    "securitySchemes": {
      "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "WLT-Api-Key"
      }
    }
  },
  "security": [
    {
      "ApiKeyAuth": []
    }
  ],
  "servers": [
    {
      "url": "https://api.atlas-beta.worldlabs.ai"
    }
  ]
}
```

