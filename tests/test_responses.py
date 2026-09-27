def test_ok_shape():
    from utils.responses import ok

    body, status = ok({"n": 1})
    assert status == 200
    assert body["code"] == "OK"
    assert body["message"] == "操作成功"
    assert body["data"] == {"n": 1}


def test_fail_maps_http_status():
    from utils.responses import fail

    body, status = fail("NOT_FOUND")
    assert status == 404
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "资源不存在"


def test_unknown_route_returns_json_404(client):
    r = client.get("/api/no-such-endpoint")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_uncaught_exception_returns_server_error(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    client = app.test_client()

    @app.route("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    r = client.get("/api/boom")
    assert r.status_code == 500
    assert r.get_json()["code"] == "SERVER_ERROR"
