from pprint import pprint
import requests
import json
from datetime import datetime
import re


class GoogleSheetClient:
    """
    A helper class to fetch and parse data from a Google Sheets document
    using the “gviz/tq” endpoint. Provides:

      • fetch_sheet_data(): 
          Dynamically read all headers in row 1, then fetch A2:⟨last_column⟩,
          returning a list of [match, {header→value, …}].

      • fetch_sheet_columns(sheet_range):
          Fetch any arbitrary range (e.g. 'A1:H100') and format the first two columns,
          converting dates/numbers/strings appropriately.
    """

    def __init__(self, sheet_url: str, sheet_title: str = "main"):
        """
        Initialize with the full sheet URL (e.g. "https://docs.google.com/spreadsheets/d/ABC123…/edit")
        and an optional sheet title (defaults to "main").
        """
        self.sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        self.sheet_title = sheet_title

    def fetch_sheet_data(self) -> list[list]:
        """
        High‐level method to read all of row 1, discover every non‐empty header,
        then fetch rows A2:⟨last_column⟩ and return a list of:
            [ match_value, { header_name: value_as_str_or_empty, … } ]

        Steps (in order):
          1) _get_column_headers() → returns ["Match", "Category 1", "Category 2", …]
          2) Compute last column letter from the number of headers
          3) _get_data_rows(last_column) → returns raw row‐objects
          4) For each row, call _parse_single_row(cells, headers)
             → skip rows whose “match” is blank
        """
        headers = self._get_column_headers()
        if not headers:
            return []

        last_col = self._column_index_to_letter(len(headers))

        raw_rows = self._get_data_rows(last_col)

        result: list[list] = []
        for row_obj in raw_rows:
            cells = row_obj.get("c", [])
            row = self._parse_single_row(cells, headers)
            result.append(row)

        return result

    def fetch_sheet_columns(self, sheet_range: str) -> list | None:
        """
        Fetches a range (e.g. 'A1:A' or 'A1:B100') and returns:
        • [val1, val2, ...] if only one column requested
        • [[val1, val2], ...] if two or more columns

        Automatically handles:
        • Dates → format using .f or as JS date
        • Numbers → convert to int if possible
        • Strings → strip
        """
        try:
            data = self._fetch_sheet_json(sheet_range)
            table = data.get("table", {})
            rows = table.get("rows", [])
            cols = table.get("cols", [])
            if not rows or not cols:
                return []

            num_cols = len(cols)
            formatted: list = []

            for row in rows:
                cells = row.get("c", [])
                row_data = []

                for idx in range(num_cols):
                    if idx >= len(cells) or cells[idx] is None:
                        row_data.append(None)
                        continue

                    cell = cells[idx]
                    col_type = cols[idx].get("type")
                    raw_val = cell.get("v")

                    if raw_val is None:
                        row_data.append(None)
                    elif col_type == "date":
                        row_data.append(self._parse_js_date(raw_val))
                    elif col_type == "number":
                        if isinstance(raw_val, float) and raw_val.is_integer():
                            row_data.append(int(raw_val))
                        else:
                            row_data.append(raw_val)
                    elif col_type == "string":
                        row_data.append(str(raw_val).strip())
                    else:
                        row_data.append(raw_val)

                if num_cols == 1:
                    formatted.append(row_data[0])
                else:
                    formatted.append(row_data)

            return formatted

        except Exception as e:
            print(f"An error occurred in fetch_sheet_columns: {e}")
            return None


    def _parse_single_row(self, cells: list[dict], headers: list[str]) -> dict[str, object] | None:
        """
        Convert a single row’s cell list into ({header: parsed_value, …}).
        Handles known fields with custom parsing:
            • blacklist → list
            • date → human-readable date
        Other values → str, int, or empty string if missing.
        """

        match_val = self._get_val(cells[3])
        if match_val in (None, ""):
            return None

        parsed: dict[str, object] = {}

        for idx in range(len(headers)):
            header_name = headers[idx].lower()
            raw_val = self._get_val(cells[idx])


            if header_name == "blacklist":
                if isinstance(raw_val, str):
                    parsed[header_name] = [item.strip() for item in raw_val.split(",") if item.strip()]
                else:
                    parsed[header_name] = []
            elif header_name == "date":
                parsed[header_name] = self._parse_js_date(raw_val)
            else:
                if raw_val is None or raw_val == "":
                    parsed[header_name] = ""
                elif isinstance(raw_val, float) and raw_val.is_integer():
                    parsed[header_name] = int(raw_val)
                else:
                    parsed[header_name] = str(raw_val).strip()

        return parsed


    def _get_column_headers(self) -> list[str]:
        """
        Read all of row 1 (range="1:1") and return a Python list of every non‐empty header string.
        Stops when the first truly blank cell is encountered.
        """
        data = self._fetch_sheet_json("1:1")
        rows = data.get("table", {}).get("rows", [])
        if not rows or not rows[0].get("c"):
            return []

        header_cells = rows[0]["c"]
        headers: list[str] = []
        for cell in header_cells:
            if cell is None or cell.get("v") in (None, ""):
                break
            headers.append(str(cell["v"]))
        return headers

    def _get_data_rows(self, last_column_letter: str) -> list[dict]:
        """
        Fetch all rows from A2 → ⟨last_column_letter⟩ and return the raw list of row‐objects.
        Each row‐object has a "c" key: a list of cell‐objects.
        """
        data_range = f"A2:{last_column_letter}"
        data = self._fetch_sheet_json(data_range)
        return data.get("table", {}).get("rows", [])


    def _fetch_sheet_json(self, cell_range: str) -> dict:
        """
        Low‐level helper to call the “gviz/tq” endpoint for a given A1‐style cell_range,
        strip off the Google‐JSAPI wrapper, and return the parsed JSON dictionary.
        """
        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/gviz/tq" \
              f"?sheet={self.sheet_title}&range={cell_range}"
        resp = requests.get(url)
        resp.raise_for_status()
        text = resp.text
        raw_json = text[47:-2]
        return json.loads(raw_json)


    @staticmethod
    def _column_index_to_letter(index: int) -> str:
        """
        Convert a 1-based column index to Excel‐style letters:
          1 → "A", 2 → "B", …, 26 → "Z", 27 → "AA", etc.
        """
        letters = []
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters.append(chr(65 + remainder))
        return "".join(reversed(letters))
    

    @staticmethod
    def _parse_js_date(js_date_str: str | None) -> str:
        """
        Converts a JavaScript-style date string like 'Date(2025,7,18)' to '18.08.2025'.
        If parsing fails, return an empty string.
        """
        if not isinstance(js_date_str, str):
            return ""

        match = re.search(r"Date\((\d+),(\d+),(\d+)\)", js_date_str)
        if not match:
            return ""

        try:
            year, month, day = map(int, match.groups())
            # JS months are 0-indexed
            date_obj = datetime(year, month + 1, day)
            return date_obj.strftime("%d.%m.%Y")
        except Exception:
            return ""
        
    @staticmethod
    def _get_val(cell: object):
        try:
            return cell.get("v") if cell is not None else None
        except (IndexError, AttributeError):
            return None


    @staticmethod
    def _parse_nullable_int(raw) -> int | None:
        """
        Attempt to convert raw to an integer. If raw is None or not parseable,
        return None.
        """
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    sheet_url = "https://docs.google.com/spreadsheets/d/1GjexKQgmF-FovbezjoO7tU844EcrhDY7spYnoinXyk8/edit?usp=sharing"
    client = GoogleSheetClient(sheet_url, "main")
    
    data = client.fetch_sheet_data()
    pprint(data)

    # sheets_proxy_url = "https://docs.google.com/spreadsheets/d/1zUpT73jHSMt6MMkB4QoMpVUAFkOWdKjM6LHx-mQccPs/edit?gid=0#gid=0"

    # proxy_client = GoogleSheetClient(sheets_proxy_url, "main")
    # print(proxy_client.fetch_sheet_columns("A1:A"))