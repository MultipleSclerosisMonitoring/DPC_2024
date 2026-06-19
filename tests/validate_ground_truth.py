import argparse
import logging
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from msGait.movement_detector import MovementDetector


MESSAGES = {
    "es": {
        "start": "Iniciando validación estadística con Ground Truth...",
        "loading": "Cargando archivo Excel: {file}",
        "processing": "Procesando {n} segmentos etiquetados...",
        "saving": "Guardando resultados en: {file}",
        "done": "Validación finalizada.",
        "summary_title": "\n--- RESULTADOS DE VALIDACIÓN ESTADÍSTICA ---",
        "accuracy": "Accuracy: {value:.4f}",
        "precision": "Precision: {value:.4f}",
        "recall": "Recall / Sensibilidad: {value:.4f}",
        "specificity": "Specificity / Especificidad: {value:.4f}",
        "f1": "F1-score: {value:.4f}",
        "kappa": "Cohen's Kappa: {value:.4f}",
        "cm": "Confusion matrix [TN FP; FN TP]:\n{value}",
    },
    "en": {
        "start": "Starting statistical validation with Ground Truth...",
        "loading": "Loading Excel file: {file}",
        "processing": "Processing {n} labeled segments...",
        "saving": "Saving results to: {file}",
        "done": "Validation finished.",
        "summary_title": "\n--- STATISTICAL VALIDATION RESULTS ---",
        "accuracy": "Accuracy: {value:.4f}",
        "precision": "Precision: {value:.4f}",
        "recall": "Recall / Sensitivity: {value:.4f}",
        "specificity": "Specificity: {value:.4f}",
        "f1": "F1-score: {value:.4f}",
        "kappa": "Cohen's Kappa: {value:.4f}",
        "cm": "Confusion matrix [TN FP; FN TP]:\n{value}",
    },
}


class GaitGroundTruthValidator:
    """Validate gait detection against a manually labeled Excel file."""

    REQUIRED_COLUMNS = {"CodeID", "from", "until", "Gait"}

    def __init__(
        self,
        excel_path: str,
        config_path: str,
        lang: str = "es",
        verbose: int = 1,
    ) -> None:
        self.lang = lang if lang in MESSAGES else "es"
        self.verbose = verbose
        self.excel_path = Path(excel_path)
        self.config_path = config_path

        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

        self._log("start")
        self._log("loading", file=str(self.excel_path))

        self.ground_truth = pd.read_excel(self.excel_path)

        missing = self.REQUIRED_COLUMNS - set(self.ground_truth.columns)
        if missing:
            raise ValueError(
                f"El Excel debe contener las columnas {sorted(self.REQUIRED_COLUMNS)}. "
                f"Faltan: {sorted(missing)}"
            )

        self.detector = MovementDetector(
            config_file=self.config_path,
            ids=[],
            verbose=0,
        )
        self._codeid_cache: dict[str, int] = {}

    def _log(self, key: str, **kwargs) -> None:
        logging.info(MESSAGES[self.lang][key].format(**kwargs))

    def close(self) -> None:
        self.detector.close()

    def _lookup_codeid_id(self, codeid: str) -> int:
        """Resolve a CodeID string to its internal PostgreSQL id."""
        if codeid in self._codeid_cache:
            return self._codeid_cache[codeid]

        with self.detector.data_manager.pg_conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM codeids WHERE codeid = %s;",
                (codeid,),
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError(f"CodeID no encontrado en PostgreSQL: {codeid}")

        codeid_id = int(row[0])
        self._codeid_cache[codeid] = codeid_id
        return codeid_id

    @staticmethod
    def _truth_to_bool(value) -> bool:
        """Normalize several truth labels to boolean."""
        if pd.isna(value):
            return False

        text = str(value).strip().lower()
        return text in {"y", "yes", "sí", "si", "true", "1"}

    def _predict_gait(self, codeid: str, start_time, end_time) -> bool:
        """Run the real algorithm for one labeled window."""
        codeid_id = self._lookup_codeid_id(codeid)

        activity_windows = pd.DataFrame(
            [
                {
                    "codeid_id": codeid_id,
                    "CodeID": codeid,
                    "foot": "Left",
                    "start_time": start_time,
                    "end_time": end_time,
                },
                {
                    "codeid_id": codeid_id,
                    "CodeID": codeid,
                    "foot": "Right",
                    "start_time": start_time,
                    "end_time": end_time,
                },
            ]
        )

        df_effective = self.detector.detect_effective_movement(
            activity_windows=activity_windows,
            output_filename=None,
            verbose=0,
        )
        df_gait = self.detector.detect_effective_gait(df_effective, verbose=0)
        df_gait_gps = self.detector.validate_gait_with_gps(df_gait, verbose=0)

        return not df_gait_gps.empty

    def evaluate(self, output_path: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Evaluate all rows from the Ground Truth Excel."""
        df = self.ground_truth.copy()

        df["from"] = (
            pd.to_datetime(df["from"], errors="coerce")
            .dt.tz_localize("Europe/Madrid", ambiguous="NaT", nonexistent="shift_forward")
            .dt.tz_convert("UTC")
        )

        df["until"] = (
            pd.to_datetime(df["until"], errors="coerce")
            .dt.tz_localize("Europe/Madrid", ambiguous="NaT", nonexistent="shift_forward")
            .dt.tz_convert("UTC")
        )

        bad_dates = df["from"].isna() | df["until"].isna()
        if bad_dates.any():
            raise ValueError(
                f"Hay filas con fechas no válidas en 'from'/'until': {df.index[bad_dates].tolist()}"
            )

        self._log("processing", n=len(df))

        y_true: list[bool] = []
        y_pred: list[bool] = []
        detailed_rows: list[dict] = []

        for idx, row in df.iterrows():
            codeid = str(row["CodeID"]).strip()
            start_time = row["from"]
            end_time = row["until"]

            actual_gait = self._truth_to_bool(row["Gait"])
            predicted_gait = self._predict_gait(codeid, start_time, end_time)

            y_true.append(actual_gait)
            y_pred.append(predicted_gait)

            detailed_rows.append(
                {
                    "row_index": idx,
                    "CodeID": codeid,
                    "from": start_time,
                    "until": end_time,
                    "Gait_true": actual_gait,
                    "Gait_pred": predicted_gait,
                    "match": actual_gait == predicted_gait,
                }
            )

        labels = [False, True]
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=labels).ravel()

        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        summary = pd.DataFrame(
            [
                {"metric": "accuracy", "value": accuracy_score(y_true, y_pred)},
                {"metric": "precision", "value": precision_score(y_true, y_pred, zero_division=0)},
                {"metric": "recall_sensitivity", "value": recall_score(y_true, y_pred, zero_division=0)},
                {"metric": "specificity", "value": specificity},
                {"metric": "f1", "value": f1_score(y_true, y_pred, zero_division=0)},
                {"metric": "cohen_kappa", "value": cohen_kappa_score(y_true, y_pred)},
                {"metric": "true_negative", "value": tn},
                {"metric": "false_positive", "value": fp},
                {"metric": "false_negative", "value": fn},
                {"metric": "true_positive", "value": tp},
                {"metric": "total_rows", "value": len(y_true)},
            ]
        )

        detailed = pd.DataFrame(detailed_rows)

        print(MESSAGES[self.lang]["summary_title"])
        print(MESSAGES[self.lang]["accuracy"].format(value=summary.loc[summary["metric"] == "accuracy", "value"].iloc[0]))
        print(MESSAGES[self.lang]["precision"].format(value=summary.loc[summary["metric"] == "precision", "value"].iloc[0]))
        print(MESSAGES[self.lang]["recall"].format(value=summary.loc[summary["metric"] == "recall_sensitivity", "value"].iloc[0]))
        print(MESSAGES[self.lang]["specificity"].format(value=summary.loc[summary["metric"] == "specificity", "value"].iloc[0]))
        print(MESSAGES[self.lang]["f1"].format(value=summary.loc[summary["metric"] == "f1", "value"].iloc[0]))
        print(MESSAGES[self.lang]["kappa"].format(value=summary.loc[summary["metric"] == "cohen_kappa", "value"].iloc[0]))
        print(MESSAGES[self.lang]["cm"].format(value=[[tn, fp], [fn, tp]]))

        report = classification_report(
            y_true,
            y_pred,
            labels=labels,
            target_names=["No Gait", "Gait"],
            zero_division=0,
        )
        print("\nClassification report:\n")
        print(report)

        detailed["from"] = detailed["from"].dt.tz_localize(None)
        detailed["until"] = detailed["until"].dt.tz_localize(None)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            self._log("saving", file=str(output_file))

            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                summary.to_excel(writer, sheet_name="summary", index=False)
                detailed.to_excel(writer, sheet_name="detailed_results", index=False)

        self._log("done")
        return summary, detailed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate gait detection against a Ground Truth Excel file."
    )
    parser.add_argument(
        "-e",
        "--excel",
        type=str,
        required=True,
        help="Path to the Ground Truth Excel file.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config.yaml.",
    )
    parser.add_argument(
        "-l",
        "--lang",
        type=str,
        choices=["es", "en"],
        default="es",
        help="Language for console output.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="tests/ground_truth_results.xlsx",
        help="Path to save validation results.",
    )
    args = parser.parse_args()

    validator = GaitGroundTruthValidator(
        excel_path=args.excel,
        config_path=args.config,
        lang=args.lang,
    )

    try:
        validator.evaluate(output_path=args.output)
    finally:
        validator.close()


if __name__ == "__main__":
    main()