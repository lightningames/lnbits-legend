from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnurlflip_ext
from .crud import (
    create_lnurlflip_pay,
    get_lnurlflip_pay,
    get_lnurlflip_pays,
    update_lnurlflip_pay,
    delete_lnurlflip_pay,
    create_lnurlflip_withdraw,
    get_lnurlflip_withdraw,
    get_lnurlflip_withdraws,
    update_lnurlflip_withdraw,
    delete_lnurlflip_withdraw,
    create_withdraw_hash_check
)
################LNURL pay

@lnurlflip_ext.route("/api/v1/links", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    try:
        return (
            jsonify(
                [
                    {**link._asdict(), **{"lnurl": link.lnurl}}
                    for link in await get_lnurlflip_pays(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_pay_link(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK


@lnurlflip_ext.route("/api/v1/links", methods=["POST"])
@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "description": {"type": "string", "empty": False, "required": True},
        "min": {"type": "number", "min": 0.01, "required": True},
        "max": {"type": "number", "min": 0.01, "required": True},
        "currency": {"type": "string", "nullable": True, "required": False},
        "comment_chars": {"type": "integer", "required": True, "min": 0, "max": 800},
        "webhook_url": {"type": "string", "required": False},
        "success_text": {"type": "string", "required": False},
        "success_url": {"type": "string", "required": False},
    }
)
async def api_link_create_or_update(link_id=None):
    if g.data["min"] > g.data["max"]:
        return jsonify({"message": "Min is greater than max."}), HTTPStatus.BAD_REQUEST

    if g.data.get("currency") == None and (
        round(g.data["min"]) != g.data["min"] or round(g.data["max"]) != g.data["max"]
    ):
        return jsonify({"message": "Must use full satoshis."}), HTTPStatus.BAD_REQUEST

    if "success_url" in g.data and g.data["success_url"][:8] != "https://":
        return (
            jsonify({"message": "Success URL must be secure https://..."}),
            HTTPStatus.BAD_REQUEST,
        )

    if link_id:
        link = await get_lnurlflip_pay(link_id)

        if not link:
            return (
                jsonify({"message": "Pay link does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if link.wallet != g.wallet.id:
            return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

        link = await update_lnurlflip_pay(link_id, **g.data)
    else:
        link = await create_lnurlflip_pay(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify({**link._asdict(), **{"lnurl": link.lnurl}}),
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@lnurlflip_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_link_delete(link_id):
    link = await get_lnurlflip_pay(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    await delete_lnurlflip_pay(link_id)

    return "", HTTPStatus.NO_CONTENT

##########LNURL withdraw

@lnurlflip_ext.route("/api/v1/withdraws", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraws():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    try:
        return (
            jsonify(
                [
                    {
                        **withdraw._asdict(),
                        **{"lnurl": withdraw.lnurl},
                    }
                    for withdraw in await get_lnurlflip_withdraws(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_retrieve(withdraw_id):
    withdraw = await get_lnurlflip_withdraw(withdraw_id, 0)

    if not withdraw:
        return (
            jsonify({"message": "lnurlflip withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your lnurlflip withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    return jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}), HTTPStatus.OK


@lnurlflip_ext.route("/api/v1/withdraws", methods=["POST"])
@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "min_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "max_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "uses": {"type": "integer", "min": 1, "required": True},
        "wait_time": {"type": "integer", "min": 1, "required": True},
        "is_unique": {"type": "boolean", "required": True},
    }
)
async def api_withdraw_create_or_update(withdraw_id=None):
    if g.data["max_lnurlflipable"] < g.data["min_lnurlflipable"]:
        return (
            jsonify(
                {
                    "message": "`max_lnurlflipable` needs to be at least `min_lnurlflipable`."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    usescsv = ""
    for i in range(g.data["uses"]):
        if g.data["is_unique"]:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if withdraw_id:
        withdraw = await get_lnurlflip_withdraw(withdraw_id, 0)
        if not withdraw:
            return (
                jsonify({"message": "lnurlflip withdraw does not exist."}),
                HTTPStatus.NOT_FOUND,
            )
        if withdraw.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your lnurlflip withdraw."}),
                HTTPStatus.FORBIDDEN,
            )
        withdraw = await update_lnurlflip_withdraw(
            withdraw_id, **g.data, usescsv=usescsv, used=0
        )
    else:
        withdraw = await create_lnurlflip_withdraw(
            wallet_id=g.wallet.id, **g.data, usescsv=usescsv
        )

    return (
        jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}),
        HTTPStatus.OK if withdraw_id else HTTPStatus.CREATED,
    )


@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_withdraw_delete(withdraw_id):
    withdraw = await get_lnurlflip_withdraw(withdraw_id)

    if not withdraw:
        return (
            jsonify({"message": "lnurlflip withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your lnurlflip withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    await delete_lnurlflip_withdraw(withdraw_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlflip_ext.route("/api/v1/withdraws/<the_hash>/<lnurl_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_hash_retrieve(the_hash, lnurl_id):
    hashCheck = await get_withdraw_hash_check(the_hash, lnurl_id)
    return jsonify(hashCheck), HTTPStatus.OK
