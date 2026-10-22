"""CSV acotado de altas: dinero decimal exacto y errores por fila."""
import csv
import hashlib
import io
import re

from app.domain.catalog import MAX_INTEGER, Record
from app.domain.identity import IdentityError

HEADERS = ["nombre", "codigo", "precio", "stock_inicial", "stock_minimo"]
MAX_BYTES = 1024 * 1024
MAX_ROWS = 500


def decimal_price(value: str) -> int:
    if not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", value):
        raise ValueError("Precio: pesos sin miles, hasta dos decimales")
    parts = re.split(r"[.,]", value)
    cents = int(parts[0]) * 100 + int(parts[1].ljust(2, "0") if len(parts) == 2 else "0")
    if cents > MAX_INTEGER:
        raise ValueError("Precio fuera del rango admitido")
    return cents


def quantity(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or len(value) > 16 or int(value) > MAX_INTEGER:
        raise ValueError("Stock: entero no negativo dentro del rango admitido")
    return int(value)


def parse_csv(content: str) -> Record:
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise IdentityError(422, "El CSV supera 1 MiB")
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rows: list[Record] = []
    errors: list[Record] = []
    try:
        reader = csv.reader(io.StringIO(content.removeprefix('\ufeff'), newline=''), delimiter=';', strict=True)
        if next(reader, None) != HEADERS:
            raise IdentityError(422, "Cabecera requerida: " + ';'.join(HEADERS))
        codes: set[str] = set()
        for number, values in enumerate(reader, start=2):
            if number > MAX_ROWS + 1:
                raise IdentityError(422, "Máximo 500 productos por CSV")
            try:
                if len(values) != 5:
                    raise ValueError("La fila debe tener cinco columnas")
                name, code, price, stock, minimum = [v.strip() for v in values]
                if not 1 <= len(name) <= 160 or '\x00' in name or len(code) > 64 or '\x00' in code:
                    raise ValueError("Nombre requerido (1–160) y código opcional de hasta 64 caracteres")
                if len(price) > 20:
                    raise ValueError("Precio fuera del rango admitido")
                item = {"name": name, "code": code or None, "price_cents": decimal_price(price),
                        "initial_stock": quantity(stock), "minimum_stock": quantity(minimum),
                        "category_id": None, "cost_cents": None}
                if code and code in codes:
                    raise ValueError("Código repetido dentro del CSV")
                if code:
                    codes.add(code)
                rows.append({"row": number, **item})
            except ValueError as exc:
                errors.append({"row": number, "message": str(exc)})
    except csv.Error as exc:
        raise IdentityError(422, "CSV mal formado") from exc
    if not rows and not errors:
        raise IdentityError(422, "El CSV no contiene productos")
    return {"source_hash": source_hash, "rows": rows, "errors": errors}
