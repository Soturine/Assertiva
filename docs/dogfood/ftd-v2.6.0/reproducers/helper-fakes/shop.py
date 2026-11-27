def publish(transport, item):
    if not item.get("approved"):
        raise PermissionError("approval required")
    return transport.send(item)
