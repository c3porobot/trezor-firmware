from micropython import const

import storage.device
from trezor import wire
from trezor.messages import ButtonRequestType
from trezor.messages.ButtonAck import ButtonAck
from trezor.messages.ButtonRequest import ButtonRequest
from trezor.messages.PassphraseAck import PassphraseAck
from trezor.messages.PassphraseRequest import PassphraseRequest
from trezor.ui import ICON_CONFIG
from trezor.ui.passphrase import CANCELLED, PassphraseKeyboard
from trezor.ui.popup import Popup
from trezor.ui.text import Text

if __debug__:
    from apps.debug import input_signal

_MAX_PASSPHRASE_LEN = const(50)


def is_enabled() -> bool:
    return storage.device.is_passphrase_enabled()


async def get(ctx: wire.Context) -> str:
    if is_enabled():
        return await request_from_user(ctx)
    else:
        return ""


async def request_from_user(ctx: wire.Context) -> str:
    passphrase = await _get_from_user(ctx)
    if len(passphrase) > _MAX_PASSPHRASE_LEN:
        raise wire.DataError("Maximum passphrase length is %d" % _MAX_PASSPHRASE_LEN)

    return passphrase


async def _get_from_user(ctx: wire.Context) -> str:
    if storage.device.get_passphrase_always_on_device():
        return await request_from_user_on_device(ctx)

    await _entry_dialog()

    request = PassphraseRequest()
    ack = await ctx.call(request, PassphraseAck)
    if ack.on_device:
        if ack.passphrase is not None:
            raise wire.DataError("Passphrase provided when it should not be")
        return await request_from_user_on_device(ctx)

    if ack.passphrase is None:
        raise wire.DataError(
            "Passphrase not provided and on_device is False. Use empty string to set an empty passphrase."
        )
    return ack.passphrase


async def request_from_user_on_device(ctx: wire.Context) -> str:
    await ctx.call(ButtonRequest(code=ButtonRequestType.PassphraseEntry), ButtonAck)

    keyboard = PassphraseKeyboard("Enter passphrase", _MAX_PASSPHRASE_LEN)
    if __debug__:
        passphrase = await ctx.wait(keyboard, input_signal())
    else:
        passphrase = await ctx.wait(keyboard)
    if passphrase is CANCELLED:
        raise wire.ActionCancelled("Passphrase entry cancelled")

    assert isinstance(passphrase, str)

    return passphrase


async def _entry_dialog() -> None:
    text = Text("Passphrase entry", ICON_CONFIG)
    text.normal("Please type your", "passphrase on the", "connected host.")
    # no need to specify timeout, because it hangs till PassphraseAck is received
    # TODO ask: not sure this is correct. If we change the behaviour of Popup
    #  (e.g. to be redrawn after the timeout expires) this will no longer display the dialog
    await Popup(text)
