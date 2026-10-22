# List operations

GET /api/v2/operations

List a project's long-running operations, newest first



```sh
curl --request GET \
  --url 'https://api.atlas-beta.worldlabs.ai/api/v2/operations' \
  --header "WLT-Api-Key: $WLT_API_KEY"
```


## Response

```json
{
  "operations": [
    {
      "id": "op_01jexample000000000000000000",
      "ownerId": "acct_01jexample00000000000000000",
      "metadata": null,
      "done": false,
      "error": null,
      "expiresAtSecs": 1789415864,
      "createdAtSecs": 1789412264,
      "webhookDelivery": {
        "state": "SCHEDULED",
        "attemptCount": 0,
        "lastAttemptTime": "2026-09-14T20:00:00Z"
      },
      "name": "accounts/acct_01jexample00000000000000000/projects/project_example/operations/op_01jexample000000000000000000"
    }
  ],
  "nextPageToken": "next-page-token"
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
    "/api/v2/operations": {
      "get": {
        "tags": [
          "operations"
        ],
        "summary": "List a project's long-running operations, newest first",
        "operationId": "list_operations_api_v2_operations_get",
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
              "description": "Only operations of this task, as named in metadata.task.",
              "title": "Task"
            },
            "description": "Only operations of this task, as named in metadata.task."
          },
          {
            "name": "status",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/OperationStatus"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Only operations with this outcome. FAILED is every done operation carrying an error, including cancelled and expired ones.",
              "title": "Status"
            },
            "description": "Only operations with this outcome. FAILED is every done operation carrying an error, including cancelled and expired ones."
          },
          {
            "name": "createdAfter",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "integer",
                  "maximum": 253402300799,
                  "minimum": 0
                },
                {
                  "type": "null"
                }
              ],
              "description": "Unix seconds; only operations accepted at or after this time.",
              "title": "Createdafter"
            },
            "description": "Unix seconds; only operations accepted at or after this time."
          },
          {
            "name": "createdBefore",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "integer",
                  "maximum": 253402300799,
                  "minimum": 0
                },
                {
                  "type": "null"
                }
              ],
              "description": "Unix seconds; only operations accepted before this time.",
              "title": "Createdbefore"
            },
            "description": "Unix seconds; only operations accepted before this time."
          },
          {
            "name": "pageSize",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 200,
              "minimum": 1,
              "default": 20,
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
                  "$ref": "#/components/schemas/ListedOperationsResponse"
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
          "permission": "operation.read"
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
      "OperationStatus": {
        "type": "string",
        "enum": [
          "RUNNING",
          "SUCCEEDED",
          "FAILED"
        ],
        "title": "OperationStatus",
        "description": "Coarse outcome filter derived from ``done`` and ``error``.\n\nFAILED is every done operation carrying an error, so cancelled and expired\noperations count as failed; ``metadata.state`` keeps the finer lifecycle\nvalue."
      },
      "ListedOperationsResponse": {
        "properties": {
          "operations": {
            "items": {
              "$ref": "#/components/schemas/ListedOperation"
            },
            "type": "array",
            "title": "Operations",
            "description": "Operations ordered from newest to oldest."
          },
          "nextPageToken": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nextpagetoken",
            "description": "Token for the next page; absent when there are no more."
          }
        },
        "type": "object",
        "required": [
          "operations"
        ],
        "title": "ListedOperationsResponse",
        "description": "A page of operations, newest first."
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
      "ListedOperation": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "Short operation id used in ``/operations/{operation}`` paths."
          },
          "ownerId": {
            "type": "string",
            "title": "Ownerid",
            "description": "Account that owns the operation."
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
            "description": "Task information and optional progress details. Use ``metadata.task`` to interpret a generic operation response, and use ``done`` to determine completion."
          },
          "done": {
            "type": "boolean",
            "title": "Done",
            "description": "Whether the operation is terminal. When true, a non-null ``error`` indicates failure; otherwise the operation succeeded."
          },
          "error": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/OperationError"
              },
              {
                "type": "null"
              }
            ],
            "description": "Failure details when ``done`` is true and the task failed; null while running and after success."
          },
          "expiresAtSecs": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Expiresatsecs",
            "description": "Task execution deadline as Unix seconds, when one is exposed. This is not an asset URL expiration."
          },
          "createdAtSecs": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Createdatsecs",
            "description": "Unix seconds when the operation was accepted."
          },
          "webhookDelivery": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/WebhookDeliverySummary"
              },
              {
                "type": "null"
              }
            ],
            "description": "Set for an operation that asked for a callback (webhookUrl). Absent on a cancelled operation, which sends no event, and when the webhook service could not be read. GET the operation's webhookDelivery for the full record."
          },
          "name": {
            "type": "string",
            "title": "Name",
            "description": "Full resource name for the operation.\n\nFor project operations:\n``accounts/{account}/projects/{project}/operations/{operation}``.\nOperation paths accept the short ``id``.",
            "readOnly": true
          }
        },
        "type": "object",
        "required": [
          "id",
          "ownerId",
          "done",
          "name"
        ],
        "title": "ListedOperation",
        "description": "An operation summary with callback progress; GET it for the result."
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
      "OperationError": {
        "properties": {
          "code": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Code",
            "description": "Numeric status code; conventionally a google.rpc.Code value."
          },
          "message": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Message",
            "description": "Developer-readable error message in English."
          },
          "details": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "type": "array",
            "title": "Details",
            "description": "Structured error details, matching google.rpc.Status.details."
          }
        },
        "type": "object",
        "title": "OperationError",
        "description": "Error payload set on a failed operation."
      },
      "WebhookDeliverySummary": {
        "properties": {
          "state": {
            "anyOf": [
              {
                "type": "string",
                "enum": [
                  "SCHEDULED",
                  "PUBLISH_FAILED"
                ]
              },
              {
                "type": "string",
                "enum": [
                  "PENDING",
                  "IN_FLIGHT",
                  "DELIVERED",
                  "SUPPRESSED",
                  "EXHAUSTED"
                ]
              }
            ],
            "title": "State",
            "description": "The state its webhookDelivery answers."
          },
          "attemptCount": {
            "type": "integer",
            "title": "Attemptcount",
            "description": "Sends attempted so far; a claim counts before its outcome.",
            "default": 0
          },
          "lastAttemptTime": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Lastattempttime"
          }
        },
        "type": "object",
        "required": [
          "state"
        ],
        "title": "WebhookDeliverySummary",
        "description": "A listed operation's callback at a glance; its webhookDelivery has the\nfull record."
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

