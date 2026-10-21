# List assets

GET /api/v2/assets

List assets in a project



```sh
curl --request GET \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/assets' \
  --header "WLT-Api-Key: $WLT_API_KEY"
```


## Response

```json
{
  "assets": [
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
  ],
  "groups": [
    {
      "operation": "op_01jexample000000000000000000",
      "task": "string",
      "assets": [
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
      ]
    }
  ],
  "nextPageToken": ""
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
      "get": {
        "tags": [
          "assets"
        ],
        "summary": "List assets in a project",
        "operationId": "list_assets_api_v2_assets_get",
        "parameters": [
          {
            "name": "origin",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/ResourceOrigin"
                },
                {
                  "type": "null"
                }
              ],
              "title": "Origin"
            }
          },
          {
            "name": "state",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/AssetState"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Filter by state. Omit for all non-deleted states.",
              "title": "State"
            },
            "description": "Filter by state. Omit for all non-deleted states."
          },
          {
            "name": "session",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets made inside this Web API session.",
              "title": "Session"
            },
            "description": "Only assets made inside this Web API session."
          },
          {
            "name": "applet",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets that came from this applet.",
              "title": "Applet"
            },
            "description": "Only assets that came from this applet."
          },
          {
            "name": "mimeType",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets of this media type. A trailing `/*`, as in `image/*`, matches every type in the family.",
              "title": "Mimetype"
            },
            "description": "Only assets of this media type. A trailing `/*`, as in `image/*`, matches every type in the family."
          },
          {
            "name": "operation",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets this Operation produced.",
              "title": "Operation"
            },
            "description": "Only assets this Operation produced."
          },
          {
            "name": "task",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets this task produced, e.g. `image2DraftSplats`.",
              "title": "Task"
            },
            "description": "Only assets this task produced, e.g. `image2DraftSplats`."
          },
          {
            "name": "producer",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/AssetProducer"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only assets made this way, e.g. `UPLOAD` for the customer's own bytes. Assets recorded before the producer was stored match no value.",
              "title": "Producer"
            },
            "description": "Only assets made this way, e.g. `UPLOAD` for the customer's own bytes. Assets recorded before the producer was stored match no value."
          },
          {
            "name": "groupBy",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/AssetGrouping"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Collect the assets under what produced them. The page then counts groups rather than assets.",
              "title": "Groupby"
            },
            "description": "Collect the assets under what produced them. The page then counts groups rather than assets."
          },
          {
            "name": "orderBy",
            "in": "query",
            "required": false,
            "schema": {
              "$ref": "#/components/schemas/AssetOrder",
              "description": "Order of the page. A grouped page orders each group by its leading asset: its newest one descending, its oldest ascending.",
              "default": "CREATE_TIME_DESC"
            },
            "description": "Order of the page. A grouped page orders each group by its leading asset: its newest one descending, its oldest ascending."
          },
          {
            "name": "pageSize",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "default": 50,
              "title": "Pagesize"
            }
          },
          {
            "name": "pageToken",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "title": "Pagetoken"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ListAssetsResponse"
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
      "ResourceOrigin": {
        "type": "string",
        "enum": [
          "APPLET",
          "DEVELOPER_API"
        ],
        "title": "ResourceOrigin",
        "description": "Product surface that created a project resource."
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
      "AssetGrouping": {
        "type": "string",
        "enum": [
          "OPERATION"
        ],
        "title": "AssetGrouping",
        "description": "What a listing collects its assets under."
      },
      "AssetOrder": {
        "type": "string",
        "enum": [
          "CREATE_TIME_DESC",
          "CREATE_TIME_ASC"
        ],
        "title": "AssetOrder",
        "description": "How a listing orders its page.\n\nA grouped page orders on each group's leading asset -- its newest running\nnewest-first, its oldest running the other way -- so a group sorts where\nits nearest asset would have in the flat listing."
      },
      "ListAssetsResponse": {
        "properties": {
          "assets": {
            "items": {
              "$ref": "#/components/schemas/Asset"
            },
            "type": "array",
            "title": "Assets",
            "description": "Assets in the selected page. Empty when the request named a grouping."
          },
          "groups": {
            "items": {
              "$ref": "#/components/schemas/AssetGroup"
            },
            "type": "array",
            "title": "Groups",
            "description": "Set only when the request named a grouping. An asset the grouping cannot place is absent - uploads and imports have no producing task - so list without a grouping to reach those."
          },
          "nextPageToken": {
            "type": "string",
            "title": "Nextpagetoken",
            "description": "Opaque token for the next page; empty on the final page.",
            "default": ""
          }
        },
        "type": "object",
        "title": "ListAssetsResponse",
        "description": "One page of a project's assets, flat or grouped.\n\n``assets`` and ``groups`` are alternatives rather than a pair: a request\nthat named no ``groupBy`` fills the first and leaves the second empty, and\none that named a grouping does the reverse. The page token pages whichever\nof the two was filled, so a grouped page counts groups."
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
      "Asset": {
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
          }
        },
        "type": "object",
        "required": [
          "id",
          "displayName",
          "mimeType"
        ],
        "title": "Asset",
        "description": "A project-owned media asset."
      },
      "AssetGroup": {
        "properties": {
          "operation": {
            "type": "string",
            "title": "Operation",
            "description": "The Operation that produced them."
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
            "description": "The task that produced them, e.g. ``image2DraftSplats``."
          },
          "assets": {
            "items": {
              "$ref": "#/components/schemas/Asset"
            },
            "type": "array",
            "title": "Assets"
          }
        },
        "type": "object",
        "required": [
          "operation"
        ],
        "title": "AssetGroup",
        "description": "The assets one Operation produced, in the page's order."
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

