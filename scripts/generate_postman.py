"""Generate a portable collection from OpenAPI without starting or changing a database."""

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def sample(schema, definitions):
    if "$ref" in schema:
        return sample(definitions[schema["$ref"].split("/")[-1]], definitions)
    if "examples" in schema:
        return schema["examples"][0]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return sample(schema["anyOf"][0], definitions)
    if schema.get("type") == "object" or "properties" in schema:
        return {
            key: sample(value, definitions)
            for key, value in schema.get("properties", {}).items()
            if key in schema.get("required", []) or "default" in value
        }
    if schema.get("type") == "array":
        return (
            [sample(schema.get("items", {}), definitions)]
            if schema.get("minItems", 0)
            else []
        )
    if schema.get("type") in ("integer", "number"):
        return schema.get("minimum", 1)
    if schema.get("type") == "boolean":
        return False
    return {
        "date": "2025-09-30",
        "date-time": "2025-10-01T12:00:00Z",
        "uuid": "11111111-1111-4111-8111-111111111111",
    }.get(schema.get("format"), "example")


def generate():
    spec = app.openapi()
    definitions = spec.get("components", {}).get("schemas", {})
    folders = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "patch", "delete", "put"}:
                continue
            tag = operation.get("tags", ["Other"])[0]
            url_path = path
            variables = []
            for parameter in operation.get("parameters", []):
                if parameter["in"] == "path":
                    name = parameter["name"]
                    url_path = url_path.replace("{" + name + "}", "{{" + name + "}}")
                    variables.append(name)
            request = {
                "method": method.upper(),
                "header": [],
                "url": "{{base_url}}" + url_path,
                "description": operation.get(
                    "description", operation.get("summary", "")
                ),
            }
            body = operation.get("requestBody", {}).get("content", {})
            if "application/json" in body:
                example = sample(body["application/json"]["schema"], definitions)
                if path.endswith("/auth/register") or path.endswith("/auth/login"):
                    example.update(
                        email="analyst@example.test",
                        password="change-this-demo-password",
                    )
                request["header"].append(
                    {"key": "Content-Type", "value": "application/json"}
                )
                request["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(example, indent=2),
                    "options": {"raw": {"language": "json"}},
                }
            elif "multipart/form-data" in body:
                request["body"] = {
                    "mode": "formdata",
                    "formdata": [
                        {"key": "file", "type": "file", "src": []},
                        {
                            "key": "metadata",
                            "type": "text",
                            "value": json.dumps(
                                {
                                    "company": "TCS",
                                    "title": "Annual report",
                                    "document_type": "annual_report",
                                    "period_start": "2025-04-01",
                                    "period_end": "2026-03-31",
                                    "basis": "consolidated",
                                }
                            ),
                        },
                    ],
                }
            success = next(
                (
                    v
                    for code, v in operation.get("responses", {}).items()
                    if code.startswith("2")
                ),
                {},
            )
            schema = (
                success.get("content", {}).get("application/json", {}).get("schema")
            )
            tests = [
                "pm.test('Successful response', () => pm.expect(pm.response.code).to.be.within(200, 299));"
            ]
            if schema:
                portable = {**schema, "definitions": definitions}
                portable = json.loads(
                    json.dumps(portable).replace(
                        "#/components/schemas/", "#/definitions/"
                    )
                )
                tests += [
                    "const schema = " + json.dumps(portable) + ";",
                    "pm.test('Response matches documented schema', () => pm.response.to.have.jsonSchema(schema));",
                ]
            if path in {"/api/auth/login", "/api/auth/register"}:
                tests.append(
                    "if (pm.response.code < 300) pm.collectionVariables.set('token', pm.response.json().access_token);"
                )
            if path == "/api/documents" and method == "get":
                tests.append(
                    "const docs = pm.response.json(); if (docs.length) pm.collectionVariables.set('document_id', docs[0].id);"
                )
            folders.setdefault(tag, []).append(
                {
                    "name": operation.get("summary", method.upper() + " " + path),
                    "request": request,
                    "event": [
                        {
                            "listen": "test",
                            "script": {"type": "text/javascript", "exec": tests},
                        }
                    ],
                }
            )
    collection = {
        "info": {
            "name": "FilingLens",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Generated from OpenAPI. Set base_url, sign in if accounts are enabled, then select a document_id. No production credentials are included.",
        },
        "variable": [
            {"key": "base_url", "value": "http://127.0.0.1:8000"},
            {"key": "token", "value": ""},
            {"key": "document_id", "value": ""},
            {"key": "page_index", "value": "0"},
            {"key": "session_id", "value": "11111111-1111-4111-8111-111111111111"},
        ],
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "const token = pm.collectionVariables.get('token'); if (token) pm.request.headers.upsert({key:'Authorization', value:'Bearer ' + token});"
                    ],
                },
            }
        ],
        "item": [
            {"name": name, "item": items} for name, items in sorted(folders.items())
        ],
    }
    path = ROOT / "docs/FilingLens.postman_collection.json"
    path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {sum(len(items) for items in folders.values())} requests")


if __name__ == "__main__":
    generate()
