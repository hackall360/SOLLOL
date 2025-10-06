import typer

app = typer.Typer(rich_markup_mode=None)  # Disable rich

@app.command()
def test(
    value1: int = typer.Option(42, help="A value"),
):
    print(f"value1={value1}")

if __name__ == "__main__":
    app()
