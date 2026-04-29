"""
Google Maps 地理資料解析應用程式主進入點

此模組負責：
1.  初始化 Flask 應用程式。
2.  設定日誌記錄。
3.  註冊 API 藍圖。
4.  提供一個工廠函數 `create_app` 來建立和設定應用程式實例。
"""

import os
from flask import Flask, jsonify

from blueprints.geo_routes import geo_bp
from modules.exceptions import GeoDataError
from utils.infra_logging import _logger


def create_app() -> Flask:
    app = Flask(__name__)

    # 註冊藍圖
    app.register_blueprint(geo_bp)

    # 註冊全域錯誤處理器
    @app.errorhandler(GeoDataError)
    def handle_geo_error(error: GeoDataError):
        """處理所有自訂的 GeoDataError。"""
        _logger.log_text(f"GeoDataError handled: {error}", severity="Error")
        response = {
            "status": "error",
            "message": "Request processing failed."
        }
        status_code = error.status_code or 500
        return jsonify(response), status_code

    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception):
        """處理所有未被捕捉的例外。"""
        _logger.log_text(f"Unhandled exception in app: {error}", severity="Error")
        response = {
            "status": "error",
            "message": "An internal server error occurred."
        }
        return jsonify(response), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)