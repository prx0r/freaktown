# Create asset

POST /api/v2/assets

Create an asset in a project



```sh
curl --request POST \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/assets' \
  --header "WLT-Api-Key: $WLT_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{
  "asset": {
    "displayName": "room.jpg",
    "url": "https://example.com/room.jpg"
  }
}'
```


## Response

```json
{
  "id": "asset_01jexample000000000000000",
  "displayName": "Example asset",
  "mimeType": "string",
  "state": "CREATED",
  "width": 1280,
  "height": 720,
  "sizeBytes": "string",
  "checksum": "string",
  "createTime": "2026-09-14T20:00:00Z",
  "type": "string",
  "parts": [
    {
      "role": "string",
      "mimeType": "string",
      "width": 1280,
      "height": 720,
      "sizeBytes": "string",
      "checksum": "string",
      "metadata": null,
      "state": "string"
    }
  ],
  "structure": {}
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
    "/api/v2/assets": {
      "post": {
        "tags": [
          "assets"
        ],
        "summary": "Create an asset in a project",
        "operationId": "create_asset_api_v2_assets_post",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/CreateAssetRequest"
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/CreateAssetResponse"
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
      "CreateAssetRequest": {
        "properties": {
          "assetId": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Assetid",
            "description": "Optional client-supplied resource id."
          },
          "asset": {
            "$ref": "#/components/schemas/AssetCreate",
            "description": "Asset metadata and ingestion source."
          }
        },
        "type": "object",
        "required": [
          "asset"
        ],
        "title": "CreateAssetRequest",
        "description": "Body of a project-owned asset-create request."
      },
      "CreateAssetResponse": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "Asset id, ``asset_<hex>``."
          },
          "displayName": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Displayname",
            "description": "User-visible label."
          },
          "mimeType": {
            "type": "string",
            "title": "Mimetype",
            "description": "Media MIME type, e.g. ``image/png``."
          },
          "state": {
            "$ref": "#/components/schemas/AssetState",
            "description": "Lifecycle state. Only ``READY`` assets can be read or used by a task.",
            "default": "CREATED"
          },
          "width": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Width",
            "description": "Pixel width when known."
          },
          "height": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Height",
            "description": "Pixel height when known."
          },
          "sizeBytes": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sizebytes",
            "description": "Size in bytes serialized as a string for large-integer compatibility with JSON consumers."
          },
          "checksum": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Checksum",
            "description": "Checksum when available."
          },
          "createTime": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Createtime",
            "description": "Server-assigned."
          },
          "type": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Type",
            "description": "Asset type, e.g. ``image``. Null for an untyped upload."
          },
          "parts": {
            "items": {
              "$ref": "#/components/schemas/AssetPart"
            },
            "type": "array",
            "title": "Parts",
            "description": "The asset's media files. Empty until the upload completes; an untyped asset then holds one part covering the whole media."
          },
          "structure": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Structure",
            "description": "What a reader needs besides the bytes."
          },
          "producedBy": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/ProducedBy"
              },
              {
                "type": "null"
              }
            ],
            "description": "How the asset came to exist, when that was recorded."
          },
          "transient": {
            "type": "boolean",
            "title": "Transient",
            "description": "True when the bytes are not retained: an upload made while the account does not retain content, or an output of an operation that purges. Both are deleted an hour after the last operation that names them finishes; an upload no operation consumes is deleted by age instead. ``contentPath`` is null for such an asset; read it through ``:createReadUrl``.",
            "default": false
          },
          "contentPath": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Contentpath",
            "description": "Already percent-encoded path for the asset. Append it unchanged to ``baseUrl`` before ``?`` and ``signedQuery``. This path does not grant access by itself. Null until the asset is ``READY`` or when unavailable; use ``assets/{asset}:createReadUrl`` as a fallback."
          },
          "url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Url",
            "description": "Unsigned content URL for the asset, ``baseUrl + contentPath``. It does not grant access by itself: the web app's read-prefix cookie authorizes it, and an API client appends ``?`` and a read prefix's ``signedQuery`` or uses ``assets/{asset}:createReadUrl`` instead. Null whenever ``contentPath`` is."
          },
          "uploads": {
            "items": {
              "$ref": "#/components/schemas/UploadGrant"
            },
            "type": "array",
            "title": "Uploads",
            "description": "One grant per declared part; empty for URL or inline ingestion."
          }
        },
        "type": "object",
        "required": [
          "id",
          "displayName",
          "mimeType"
        ],
        "title": "CreateAssetResponse",
        "description": "The new asset, plus a grant for every part it declared."
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
      "AssetCreate": {
        "properties": {
          "displayName": {
            "anyOf": [
              {
                "type": "string",
                "maxLength": 256
              },
              {
                "type": "null"
              }
            ],
            "title": "Displayname",
            "description": "User-visible label."
          },
          "session": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Session",
            "description": "The Web API session this upload belongs to. The session must be in the same project; the asset inherits its applet."
          },
          "type": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Type",
            "description": "Asset type, e.g. ``image``. Decides which part roles the asset may carry and what each may hold. Omit for a single untyped object uploaded through ``:createUploadUrl``."
          },
          "parts": {
            "items": {
              "$ref": "#/components/schemas/AssetPartDeclaration"
            },
            "type": "array",
            "title": "Parts",
            "description": "The parts to be uploaded. One grant comes back per part."
          },
          "structure": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Structure",
            "description": "What a reader needs besides the bytes, in the shape the asset type defines, e.g. an image's camera."
          },
          "base64": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Base64",
            "description": "Bytes carried in the request, optionally as a ``data:`` URL. The asset comes back ``READY``. Capped at 10 MiB decoded; above that, declare a part and upload to its grant."
          },
          "url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Url",
            "description": "A public URL the platform fetches. The asset comes back ``READY``."
          }
        },
        "type": "object",
        "title": "AssetCreate",
        "description": "Client-provided fields for creating a project-owned asset."
      },
      "AssetState": {
        "type": "string",
        "enum": [
          "CREATED",
          "UPLOADING",
          "READY",
          "DELETED"
        ],
        "title": "AssetState"
      },
      "AssetPart": {
        "properties": {
          "role": {
            "type": "string",
            "title": "Role",
            "description": "What the part holds, e.g. ``rgb``."
          },
          "mimeType": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Mimetype",
            "description": "Media type read off the bytes."
          },
          "width": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Width",
            "description": "Pixel width when known."
          },
          "height": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Height",
            "description": "Pixel height when known."
          },
          "sizeBytes": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sizebytes",
            "description": "Size in bytes serialized as a string for large-integer compatibility with JSON consumers."
          },
          "checksum": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Checksum",
            "description": "Checksum when available."
          },
          "metadata": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Metadata",
            "description": "The role's own contract, e.g. a depth encoding."
          },
          "state": {
            "type": "string",
            "title": "State",
            "description": "``CREATED`` until the bytes arrive."
          }
        },
        "type": "object",
        "required": [
          "role",
          "state"
        ],
        "title": "AssetPart",
        "description": "One media file belonging to an asset."
      },
      "ProducedBy": {
        "properties": {
          "producer": {
            "$ref": "#/components/schemas/AssetProducer",
            "description": "The act that made the asset."
          },
          "origin": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/ResourceOrigin"
              },
              {
                "type": "null"
              }
            ],
            "description": "The product surface the act came through."
          },
          "applet": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Applet",
            "description": "The applet the asset came from, e.g. ``turntable``. Set for Web API work whose session named one."
          },
          "session": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Session",
            "description": "The Web API session the asset was made inside."
          },
          "task": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Task",
            "description": "The task that produced it, e.g. ``image2DraftSplats``."
          },
          "operation": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Operation",
            "description": "The Operation that produced it."
          }
        },
        "type": "object",
        "required": [
          "producer"
        ],
        "title": "ProducedBy",
        "description": "How the asset came to exist.\n\nPresent on every asset whose provenance was recorded. ``producer`` says\nwhich act made it, and the rest qualify that act: ``task`` and\n``operation`` are set only for ``TASK``, and ``applet`` and ``session``\nonly for work done through the Web API."
      },
      "UploadGrant": {
        "properties": {
          "role": {
            "type": "string",
            "title": "Role",
            "description": "Declared asset-part role this upload fills."
          },
          "method": {
            "type": "string",
            "title": "Method",
            "description": "HTTP verb to use for the upload, e.g. PUT."
          },
          "url": {
            "type": "string",
            "title": "Url",
            "description": "Short-lived upload URL. Send the bytes here without the World Labs API key."
          },
          "headers": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object",
            "title": "Headers",
            "description": "Headers the client MUST include on the upload request."
          },
          "expiresAt": {
            "type": "string",
            "format": "date-time",
            "title": "Expiresat",
            "description": "When this upload grant expires; create a new one after."
          }
        },
        "type": "object",
        "required": [
          "role",
          "method",
          "url",
          "expiresAt"
        ],
        "title": "UploadGrant",
        "description": "Permission to upload one asset part."
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
      },
      "AssetPartDeclaration": {
        "properties": {
          "role": {
            "type": "string",
            "title": "Role",
            "description": "Role this file fills in the asset type, e.g. ``rgb``, ``mask`` or ``depth``."
          },
          "contentType": {
            "type": "string",
            "title": "Contenttype",
            "description": "MIME type that will be sent with the upload, e.g. ``image/png``."
          },
          "contentLength": {
            "type": "integer",
            "maximum": 1073741824,
            "title": "Contentlength",
            "description": "Upload size in bytes, serialized on the wire as a string. Capped at 1 GiB."
          },
          "metadata": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Metadata",
            "description": "The role's own contract, e.g. a depth encoding."
          }
        },
        "type": "object",
        "required": [
          "role",
          "contentType",
          "contentLength"
        ],
        "title": "AssetPartDeclaration",
        "description": "A part the client intends to upload.\n\nThe upload must use the declared content type and contain exactly the\ndeclared number of bytes."
      },
      "AssetProducer": {
        "type": "string",
        "enum": [
          "UPLOAD",
          "IMPORT",
          "TASK"
        ],
        "title": "AssetProducer",
        "description": "The act that produced an asset.\n\nA customer's own bytes are an UPLOAD however they arrived; bytes we\nfetched from an address they gave us are an IMPORT; a task's output is a\nTASK."
      },
      "ResourceOrigin": {
        "type": "string",
        "enum": [
          "APPLET",
          "DEVELOPER_API"
        ],
        "title": "ResourceOrigin",
        "description": "Product surface that created a project resource."
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

