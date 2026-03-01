import os
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

SUPABASE_URL = os.getenv("SUPABASE_URL")
JWKS_URL     = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

_jwks_cache: Optional[dict] = None

bearer_scheme = HTTPBearer(auto_error=False)


async def get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        response = await client.get(JWKS_URL)
        response.raise_for_status()
        _jwks_cache = response.json()
        print(f"✅ Auth: JWKS loaded from {JWKS_URL}")
        return _jwks_cache


def get_public_key(jwks: dict, kid: str) -> Optional[dict]:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> tuple[str, str]:
    """
    Verifies the Supabase JWT and returns (user_id, raw_token).

    Returns both so endpoints can:
      - Use user_id for business logic
      - Pass raw_token to Supabase client so auth.uid() resolves for RLS

    Usage in endpoints:
        user_id, token = Depends(verify_token)
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Please log in.",
        )

    token = credentials.credentials

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "ES256")

        if not kid:
            raise HTTPException(status_code=401, detail="Invalid token: missing kid")

        jwks       = await get_jwks()
        public_key = get_public_key(jwks, kid)

        if not public_key:
            raise HTTPException(status_code=401, detail="Invalid token: signing key not found")

        payload = jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )

        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")

        return user_id, token   # ← return both

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {str(e)}")