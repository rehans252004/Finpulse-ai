from flask import Blueprint, jsonify, request, send_file

from .report_service import create_csv, create_excel, create_pdf

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/<report_format>")
def download_report(report_format):
    report_format = report_format.strip().lower()

    try:
        if report_format == "pdf":
            output = create_pdf()
            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="market-report.pdf",
            )

        if report_format == "csv":
            tableau_ready = request.args.get("tableau", "").lower() in {
                "1", "true", "yes"
            }
            output = create_csv(tableau_ready=tableau_ready)
            return send_file(
                output,
                mimetype="text/csv",
                as_attachment=True,
                download_name="market-report.csv",
            )

        if report_format in {"xlsx", "excel"}:
            output = create_excel()
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="market-report.xlsx",
            )

        return jsonify(error="Format must be pdf, csv, or xlsx."), 400

    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
    except Exception:
        bp.logger.exception("Market report export failed")
        return jsonify(error="Could not create the market report."), 500