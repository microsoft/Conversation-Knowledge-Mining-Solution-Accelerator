import base64
import json
import logging


def get_authenticated_user_details(request_headers):
    """
    Extract authenticated user details from EasyAuth request headers.

    When App Service Easy Auth is configured the real AAD identity headers are
    present and returned directly.  When Easy Auth is NOT configured (local dev
    or unauthenticated) the function falls back to sample_user so the app keeps
    working without a login wall — consistent with other GSA repos.

    Args:
        request_headers: The HTTP request headers (dict-like, case-insensitive).

    Returns:
        dict with keys: user_principal_id, user_name, auth_provider,
                        auth_token, client_principal_b64, aad_id_token
    """
    user_object = {}

    # EasyAuth injects headers with lowercase keys; check for the principal ID.
    if "x-ms-client-principal-id" not in request_headers:
        logging.info("No EasyAuth headers found — falling back to sample user")
        from . import sample_user
        raw_user_object = sample_user.sample_user
    else:
        raw_user_object = {k: v for k, v in request_headers.items()}

    normalized = {k.lower(): v for k, v in raw_user_object.items()}

    user_object["user_principal_id"] = normalized.get("x-ms-client-principal-id")
    user_object["user_name"] = normalized.get("x-ms-client-principal-name")
    user_object["auth_provider"] = normalized.get("x-ms-client-principal-idp")
    user_object["auth_token"] = normalized.get("x-ms-token-aad-id-token")
    user_object["client_principal_b64"] = normalized.get("x-ms-client-principal")
    user_object["aad_id_token"] = normalized.get("x-ms-token-aad-id-token")

    return user_object


def get_tenantid(client_principal_b64):
    """
    Extract the tenant ID from the base64-encoded X-Ms-Client-Principal header.
    """
    logger = logging.getLogger(__name__)
    tenant_id = ""
    if client_principal_b64:
        try:
            decoded_bytes = base64.b64decode(client_principal_b64)
            decoded_string = decoded_bytes.decode("utf-8")
            user_info = json.loads(decoded_string)
            tenant_id = user_info.get("tid", "")
        except Exception as ex:
            logger.exception(ex)
    return tenant_id
