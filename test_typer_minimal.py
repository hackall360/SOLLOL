import typer
from typing import Optional

app = typer.Typer()

@app.command()
def test(
    value1: Optional[str] = typer.Option(default=None, help="A value"),
):
    print(f"value1={value1}")

if __name__ == "__main__":
    app()
