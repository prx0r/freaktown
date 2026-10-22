# Create upload URL

POST /api/v2/assets/{asset}:createUploadUrl

Mint a signed upload URL for an asset



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/assets/asset_01jexample000000000000000:createUploadUrl' \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{
  "contentType": "image/png",
  "contentLength": 1
}'
```


## Response

```json
{
  "uploadUrl": "https://example.com/image.png",
  "method": "string",
  "expiresAt": "2026-09-14T20:00:00Z",
  "headers": {}
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
    "/api/v2/assets/{asset}:createUploadUrl": {
      "post": {
        "tags": [
          "assets"
        ],
        "summary": "Mint a signed upload URL for an asset",
        "operationId": "create_upload_url_api_v2_assets__asset__createUploadUrl_post",
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
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/CreateUploadUrlRequest"
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/CreateUploadUrlResponse"
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
          "permission": "asset.create"
        }
      }
    }
  },
  "components": {
    "schemas": {
      "CreateUploadUrlRequest": {
        "properties": {
          "contentType": {
            "type": "string",
            "title": "Contenttype"
          },
          "contentLength": {
            "type": "integer",
            "maximum": 1073741824,
            "title": "Contentlength",
            "description": "Expected upload size in bytes, serialized on the wire as a string. Capped at 1 GiB."
          }
        },
        "type": "object",
        "required": [
          "contentType",
          "contentLength"
        ],
        "title": "CreateUploadUrlRequest",
        "description": "Body of an ``:createUploadUrl`` request.\n\n``content_length`` is the wire-format string the API contract requires\n(JSON's large-integer limitation); the validator parses it to an int so\nhandlers can pass it to the service layer untouched."
      },
      "CreateUploadUrlResponse": {
        "properties": {
          "uploadUrl": {
            "type": "string",
            "title": "Uploadurl",
            "description": "Short-lived upload URL. Send the bytes here without the World Labs API key."
          },
          "method": {
            "type": "string",
            "title": "Method",
            "description": "HTTP verb to use for the upload, e.g. PUT."
          },
          "expiresAt": {
            "type": "string",
            "format": "date-time",
            "title": "Expiresat",
            "description": "When this upload grant expires; create a new one after."
          },
          "headers": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object",
            "title": "Headers",
            "description": "Headers the client MUST include on the upload request."
          }
        },
        "type": "object",
        "required": [
          "uploadUrl",
          "method",
          "expiresAt"
        ],
        "title": "CreateUploadUrlResponse",
        "description": "Upload ticket for a project-owned Asset."
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

