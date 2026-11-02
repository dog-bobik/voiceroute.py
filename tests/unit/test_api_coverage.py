from scripts.check_api_coverage import operations


def test_operations_respect_operation_level_auth_and_inherited_auth() -> None:
    document = {
        "security": [{"botToken": []}],
        "paths": {
            "/messages": {"post": {"operationId": "sendMessage"}},
            "/profile": {
                "get": {
                    "operationId": "getProfile",
                    "security": [{"humanSession": []}, {"botToken": []}],
                }
            },
            "/operator": {"get": {"operationId": "getOperator", "security": [{"admin": []}]}},
        },
    }

    result = {item["operationId"]: item for item in operations(document)}

    assert result["sendMessage"]["status"] == "review-required"
    assert result["getProfile"]["status"] == "review-required"
    assert result["getOperator"]["status"] == "excluded-auth"


def test_public_operation_is_in_inventory() -> None:
    result = operations({"paths": {"/capabilities": {"get": {"operationId": "capabilities"}}}})
    assert result == [
        {
            "operationId": "capabilities",
            "method": "GET",
            "path": "/capabilities",
            "auth": "public",
            "status": "review-required",
        }
    ]
