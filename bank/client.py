"""Async client for the shadybank HTTP API.

This is the only thing in ShadyPredict that talks to shadybank. The market itself
never calls the bank per-bet; it uses this client for two flows only:

  * deposit  -> authorize() + capture()   (pull bucks from a card into the house account)
  * cash-out -> credit()                  (push bucks from the house back to a card)

The bank speaks form-encoded POST bodies and returns plaintext for some endpoints
(login token, auth code) and JSON for others (balance, transactions). Auth is a
bearer token from login().

Verified against Shadytel/shadybank @ trunk (src/apiserver.py).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import httpx


class ShadyBankError(Exception):
    """Raised when the bank returns a non-success status."""

    def __init__(self, message: str, *, status: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _fmt_amount(amount: "Decimal | float | int") -> str:
    # The bank does round(float(amount), 2); send exactly two decimals.
    return f"{Decimal(str(amount)):.2f}"


class ShadyBankClient:
    def __init__(self, base_url: str, *, client: Optional[httpx.AsyncClient] = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "ShadyBankClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ---- low-level helpers -------------------------------------------------
    def _auth(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    async def _post(self, path: str, data: dict[str, str], token: Optional[str] = None) -> httpx.Response:
        headers = self._auth(token) if token else {}
        return await self._client.post(f"{self.base_url}{path}", data=data, headers=headers)

    @staticmethod
    def _require(resp: httpx.Response, expected: int, what: str) -> httpx.Response:
        if resp.status_code != expected:
            raise ShadyBankError(
                f"{what} failed: HTTP {resp.status_code} {resp.text!r}",
                status=resp.status_code,
                body=resp.text,
            )
        return resp

    # ---- auth --------------------------------------------------------------
    async def login(
        self,
        *,
        pan: Optional[str] = None,
        account_id: Optional[int] = None,
        otp: Optional[str] = None,
        pin: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        """Authenticate and return a bearer token.

        Identify by `pan` (card number) or `account_id`, plus exactly one secret:
        `otp` (TOTP), `pin`, or `password`. For ShadyPredict, users log in with pan+otp.
        """
        data: dict[str, str] = {}
        if pan:
            data["pan"] = pan
        if account_id is not None:
            data["account_id"] = str(account_id)
        if otp:
            data["otp"] = otp
        if pin:
            data["pin"] = pin
        if password:
            data["password"] = password
        resp = self._require(await self._post("/api/login", data), 201, "login")
        return resp.text.strip()

    async def logout(self, token: str) -> None:
        await self._post("/api/logout", {}, token)

    # ---- read --------------------------------------------------------------
    async def balance(self, token: str) -> dict[str, Any]:
        resp = await self._client.get(f"{self.base_url}/api/balance", headers=self._auth(token))
        self._require(resp, 200, "balance")
        return resp.json()

    async def transactions(self, token: str) -> list[dict[str, Any]]:
        resp = await self._client.get(f"{self.base_url}/api/transactions", headers=self._auth(token))
        self._require(resp, 200, "transactions")
        return resp.json()

    # ---- merchant: pull money in (deposit) ---------------------------------
    async def authorize(
        self,
        merchant_token: str,
        amount: "Decimal | float | int",
        *,
        pan: Optional[str] = None,
        otp: Optional[str] = None,
        shotp: Optional[str] = None,
        magstripe: Optional[str] = None,
        nfc_token: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Place a hold on a customer's card. Returns a 6-digit auth code.

        Customer is identified by pan+otp (web), magstripe (booth swipe), or nfc_token.
        """
        data: dict[str, str] = {"amount": _fmt_amount(amount)}
        if pan:
            data["pan"] = pan
        if otp:
            data["otp"] = otp
        if shotp:
            data["shotp"] = shotp
        if magstripe:
            data["magstripe"] = magstripe
        if nfc_token:
            data["nfc_token"] = nfc_token
        if description:
            data["description"] = description
        resp = self._require(await self._post("/api/authorize", data, merchant_token), 200, "authorize")
        return resp.text.strip()

    async def capture(
        self,
        merchant_token: str,
        auth_code: str,
        amount: "Decimal | float | int",
        *,
        description: Optional[str] = None,
    ) -> None:
        """Finalize a hold: move the funds into the merchant account."""
        data: dict[str, str] = {"auth_code": auth_code, "amount": _fmt_amount(amount)}
        if description:
            data["description"] = description
        self._require(await self._post("/api/capture", data, merchant_token), 204, "capture")

    async def void(self, merchant_token: str, auth_code: str) -> None:
        """Cancel a pending (uncaptured) hold."""
        self._require(await self._post("/api/void", {"auth_code": auth_code}, merchant_token), 204, "void")

    async def reverse(self, merchant_token: str, auth_code: str, *, description: Optional[str] = None) -> None:
        """Refund a captured transaction."""
        data: dict[str, str] = {"auth_code": auth_code}
        if description:
            data["description"] = description
        self._require(await self._post("/api/reverse", data, merchant_token), 204, "reverse")

    # ---- merchant: push money out (cash-out / payout) ----------------------
    async def credit(
        self,
        merchant_token: str,
        amount: "Decimal | float | int",
        *,
        pan: Optional[str] = None,
        magstripe: Optional[str] = None,
        nfc_token: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Send funds from the merchant account to a customer card.

        Requires merchant available >= amount unless the merchant is partner/admin/special.
        """
        data: dict[str, str] = {"amount": _fmt_amount(amount)}
        if pan:
            data["pan"] = pan
        if magstripe:
            data["magstripe"] = magstripe
        if nfc_token:
            data["nfc_token"] = nfc_token
        if description:
            data["description"] = description
        self._require(await self._post("/api/credit", data, merchant_token), 204, "credit")
