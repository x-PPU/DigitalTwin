import sys
from pathlib import Path
import pandas as pd


class ProcessSkillChecker:
    """
    Apply whole-value replacements on ReferenceElement rows in Process_base.csv,
    write the updated Process.csv, and verify against Skill.csv (idShort).
    Only prints unmatched lines; no extra report file is written.
    """

    def __init__(self, project_root=None, custom_value_map=None):
        # paths
        self.project_root = (project_root or Path(__file__).resolve().parent).resolve()
        self.check_dir = (self.project_root / "check").resolve()
        self.output_dir = (self.project_root / "output").resolve()

        self.process_base_csv = self.output_dir / "Process_base.csv"
        self.process_out_csv = self.check_dir / "Process_check.csv"
        self.skill_csv = self.check_dir / "Skill.csv"

        # expected Process schema
        self.required_cols = [
            "typeName",
            "idShort",
            "value",
            "valueType",
            "category",
            "descriptionEN",
            "descriptionDE",
            "semanticId",
        ]

        # whole-value replacement dict (exact match). extend as needed
        self.custom_value_map = custom_value_map or {
            "LargeSortingConveyor_Skill_ConveyorForward": "Conveyor_Skill_ConveyorForward",
            "LargeSortingConveyor_Skill_ConveyorStop": "Conveyor_Skill_ConveyorStop",
            "SmallSortingConveyor_Skill_ConveyorForward": "Conveyor_Skill_ConveyorForward",
            "SmallSortingConveyor_Skill_ConveyorStop": "Conveyor_Skill_ConveyorStop",
            "RefeedingConveyor_Skill_ConveyorForward": "Conveyor_Skill_ConveyorForward",
            "RefeedingConveyor_Skill_ConveyorStop": "Conveyor_Skill_ConveyorStop",
            "PicAlphaConveyor_Skill_ConveyorForward": "Conveyor_Skill_ConveyorForward",
            "PicAlphaConveyor_Skill_ConveyorStop": "Conveyor_Skill_ConveyorStop",
            "stampingCylinder_Skill_Extend": "MonostableCylinder_Skill_Extend",
            "stampingCylinder_Skill_Retract": "MonostableCylinder_Skill_Retract",
        }

        self.df_base = None
        self.df_skill = None
        self.df_proc = None

    def load_csv(self, path):
        """Load CSV with robust encoding handling."""
        for enc in ("utf-8-sig", "utf-8"):
            try:
                return pd.read_csv(path, dtype=str, encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(path, dtype=str)

    def strip_df(self, df):
        """Trim whitespace for object columns (avoid deprecated applymap)."""
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
        return df

    def norm(self, s):
        """Normalize for case-insensitive matching."""
        return (s or "").strip().casefold()

    def validate_inputs(self):
        """Ensure required files and columns exist."""
        if not self.process_base_csv.exists() or not self.skill_csv.exists():
            print("[error] missing input files:")
            print(" process_base.csv:", self.process_base_csv)
            print(" skill.csv       :", self.skill_csv)
            sys.exit(1)

        self.df_base = self.strip_df(self.load_csv(self.process_base_csv))
        self.df_skill = self.strip_df(self.load_csv(self.skill_csv))

        missing = [c for c in self.required_cols if c not in self.df_base.columns]
        if missing:
            print(f"[error] Process_base.csv is missing columns: {missing}")
            sys.exit(1)

        if "idShort" not in self.df_skill.columns:
            print("[error] Skill.csv is missing column: ['idShort']")
            sys.exit(1)

    def apply_value_replacements(self):
        """Apply whole-value replacements on ReferenceElement rows, skipping MAIN_m_container* values."""
        self.df_proc = self.df_base.copy()

        # only ReferenceElement
        mask_ref = self.df_proc["typeName"] == "ReferenceElement"
        # skip those starting with MAIN_m_container
        value_series = self.df_proc["value"].fillna("").astype(str)
        mask_skip = value_series.str.startswith("MAIN_m_container")
        mask_apply = mask_ref & ~mask_skip

        def replace_value(v):
            v = (v or "").strip()
            return self.custom_value_map.get(v, v)
        self.df_proc.loc[mask_apply, "value"] = self.df_proc.loc[mask_apply, "value"].apply(replace_value)

    def write_process_csv(self):
        """Write updated Process.csv."""
        self.df_proc.to_csv(self.process_out_csv, index=False, encoding="utf-8-sig")
        print(f"[info] new Process.csv written → {self.process_out_csv}")

    def check_against_skill(self):
        """
        Check updated values against Skill.idShort with case-insensitive matching.
        Skips ReferenceElement rows whose value starts with MAIN_m_container.
        Prints unmatched entries only.
        """
        skill_ids = set(self.df_skill["idShort"].dropna().astype(str).map(self.norm))

        df_refs = self.df_proc[self.df_proc["typeName"] == "ReferenceElement"].copy()
        df_refs = df_refs[~df_refs["value"].fillna("").astype(str).str.startswith("MAIN_m_container")]

        not_found = []
        checked = 0

        for idx, row in df_refs.iterrows():
            checked += 1
            used_value = (row.get("value") or "").strip()
            lookup = used_value.replace("_", ".", 1) if used_value else ""
            if self.norm(lookup) not in skill_ids:
                # no print for skipped rows
                not_found.append(
                    (idx + 2, (row.get("idShort") or "").strip(), used_value, lookup)
                )

        if not_found:
            print("ReferenceElement rows not found in Skill.idShort "
                "(whole-value replacement only, case-insensitive, first '_'→'.'):")
            for line_no, id_short, value_used, lookup_key in not_found:
                print(f"line {line_no}\t| idShort: {id_short}\t| value: {value_used}")
            print(f"\nunmatched total: {len(not_found)} / checked: {checked}")
        else:
            print(f"all matched. checked: {checked}")

    def run(self):
        self.validate_inputs()
        self.apply_value_replacements()
        self.write_process_csv()
        self.check_against_skill()


def main():

    checker = ProcessSkillChecker()
    checker.run()


if __name__ == "__main__":
    main()
