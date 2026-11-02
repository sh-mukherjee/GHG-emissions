# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0; sys_platform != 'emscripten'",
#     "altair>=5.5; sys_platform == 'emscripten'",
#     "marimo",
#     "pandas==2.3.2; sys_platform != 'emscripten'",
#     "pandas>=2.2; sys_platform == 'emscripten'",
#     "pyarrow",
# ]
# ///
#
# Data is bundled as `public/ghg.parquet` so the app never calls the OECD SDMX
# API at runtime. Rebuild the snapshot with:  uv run scripts/snapshot.py

import marimo

__generated_with = "0.15.1"
app = marimo.App(width="full", app_title="oecd-ghg-emissions")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import altair as alt
    import pandas as pd

    return alt, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Source: the [OECD SDMX API](https://sdmx.oecd.org) - dataflow `OECD.CFE.EDS:DSD_REG_CLIM@DF_GHG(2.4)`, *Greenhouse gas emissions - Regions*. Browse it in the [OECD Data Explorer](https://data-explorer.oecd.org).""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Load the GHG emissions snapshot

The data is pre-downloaded into `public/ghg.parquet` by `scripts/snapshot.py`, so
the app starts instantly instead of waiting on a live API call. To refresh it,
run `uv run scripts/snapshot.py` (or let the scheduled GitHub Action do it).
""")
    return


@app.cell
async def _(mo, pd):
    import sys
    from io import BytesIO
    from pathlib import Path

    data_url = mo.notebook_location() / "public" / "ghg.parquet"

    if sys.platform == "emscripten":
        # In the browser there is no filesystem: fetch the bundled file over HTTP.
        from pyodide.http import pyfetch

        response = await pyfetch(str(data_url))
        response.raise_for_status()
        df = pd.read_parquet(BytesIO(await response.bytes()))
    else:
        path = Path(data_url)
        if not path.exists():
            raise FileNotFoundError(
                f"Missing data snapshot at {path}.\n"
                "Build it with:  uv run scripts/snapshot.py"
            )
        df = pd.read_parquet(path)

    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Define the list of countries and input widgets to select a single country or multiple countries""")
    return


@app.cell
def _(df, mo):
    countries = sorted(df["Country"].unique().tolist())

    Country = mo.ui.dropdown(
        options=countries,
        value="United States" if "United States" in countries else countries[0],
        label="Country",
    )

    default_countries = [
        c
        for c in ["United States", "China (People's Republic of)", "India"]
        if c in countries
    ]
    Countries = mo.ui.multiselect(
        options=countries,
        value=default_countries or countries[:3],
        label="Select Countries",
    )
    return Countries, Country, countries


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Define the list of GHG emission sectors and input widgets to select the sector""")
    return


@app.cell
def _(df, mo):
    sectors = sorted(df["Measure"].unique().tolist())

    default_sector = "GHG emissions from agriculture"
    Sector = mo.ui.dropdown(
        options=sectors,
        value=default_sector if default_sector in sectors else sectors[0],
        label="Sector",
    )

    default_sectors = [
        s
        for s in ["GHG emissions from agriculture", "GHG emissions from manufacturing"]
        if s in sectors
    ]
    Sectors = mo.ui.multiselect(
        options=sectors,
        value=default_sectors or sectors[:2],
        label="Select Sectors",
    )
    return Sector, Sectors, sectors


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Define the list of units of measurement""")
    return


@app.cell
def _(df, mo):
    units = sorted(df["Unit of measure"].unique().tolist())

    default_unit = "Tonnes of CO2-equivalent"
    Units = mo.ui.radio(
        options=units,
        value=default_unit if default_unit in units else units[0],
        label="Choose One",
    )
    return (Units,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Charts to show the selected data""")
    return


@app.cell
def _(Countries, Sector, Units, alt, countries, df):
    # Colour mappings for countries. Cycling the palette guarantees every
    # country gets a colour, even if the dataset grows past the palette length.
    palette_country = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c', '#98df8a', '#d62728', '#ff9896', '#9467bd', '#FF0000', '#c5b0d5', '#8c564b', '#c49c94', '#e377c2', '#f7b6d2', '#7f7f7f', '#c7c7c7', '#bcbd22', '#dbdb8d', '#17becf', '#9edae5', '#a6cee3', '#1f78b4', '#b2df8a', '#FF8C00', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6', '#6a3d9a', '#ffff99', '#b15928', '#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#66a61e', '#e6ab02', '#a6761d', '#666666', '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#00008B', '#f781bf']
    country_color_map = {
        country: palette_country[i % len(palette_country)]
        for i, country in enumerate(countries)
    }

    # set the mask for the selected countries and selected sector
    mask = (
        df["Country"].isin(Countries.value)
        & (df["Measure"] == Sector.value)
        & (df["Unit of measure"] == Units.value)
    )

    # filter the dataframe df using the mask
    filtered_df = df.loc[mask]

    # We get the list of unique countries from the filtered DataFrame
    # and use that as the domain for the scale.
    domain_country_filtered = filtered_df["Country"].unique().tolist()
    range_country_filtered = [country_color_map[c] for c in domain_country_filtered]

    trends_chart = (
        alt.Chart(filtered_df)
        .mark_line()
        .encode(
            # X-axis: Year
            x=alt.X("Year"),
            # Y-axis: Value
            y=alt.Y("Value:Q", scale=alt.Scale(zero=False)),
            # Color: Based on "Country"
            color=alt.Color("Country").scale(domain=domain_country_filtered, range=range_country_filtered),
            # Tooltips: Show data columns on hover
            tooltip=["Year", "Country", "Measure", "Unit of measure", "Value"],
        )
        .properties(title="Annual Trends in GHG Emissions")
    ).interactive()  # Allows zooming and panning
    return (trends_chart,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""##Build the dashboard layout""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""###Data Tab""")
    return


@app.cell
def _(mo):
    data_text = mo.md(
        f"""
    # OECD Data on GHG Emissions by Country -- Per Sector, Total and Total per Person

    The original source for this data is [OECD Regions, Cities and Local Areas database](http://oe.cd/geostats).
        """
    ).callout()
    return (data_text,)


@app.cell
def _(data_text, df, mo):
    Data = mo.vstack([data_text, mo.ui.table(df, page_size=20)])
    return (Data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Annual Trends Tab""")
    return


@app.cell
def _(Countries, Sector, Units, mo, trends_chart):
    Trends = mo.vstack([mo.hstack([Countries, Sector, Units]), trends_chart])
    return (Trends,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### Annual Snapshot Tabs""")
    return


@app.cell
def _(df, mo):
    years = sorted(df["Year"].unique().tolist())
    year_picker = mo.ui.dropdown(options=years, value=years[-1], label="Year")
    return (year_picker,)


@app.cell
def _(Country, Sector, Units, alt, df, sectors, year_picker):
    # set colours for the different emission sectors
    palette_sector = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6', '#6a3d9a', '#ffff99', '#b15928']
    sector_color_map = {
        sector: palette_sector[i % len(palette_sector)]
        for i, sector in enumerate(sectors)
    }

    year_country_mask = (
        (df["Country"] == Country.value)
        & (df["Year"] == year_picker.value)
        & (df["Unit of measure"] == Units.value)
    )
    year_country_df = df.loc[year_country_mask]
    domain_sector_filtered = year_country_df["Measure"].unique().tolist()
    range_sector_filtered = [sector_color_map[s] for s in domain_sector_filtered]

    year_country_chart = alt.Chart(year_country_df).mark_bar().encode(
        x=alt.X("Measure:N", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("Value:Q"),
        color=alt.Color("Measure:N").scale(domain=domain_sector_filtered, range=range_sector_filtered).legend(None),
        # Tooltips: Show data columns on hover
        tooltip=["Year", "Country", "Measure", "Unit of measure", "Value"],
    ).properties(title="Annual Snapshot of GHG Emissions for a Country")

    year_sector_mask = (
        (df["Measure"] == Sector.value)
        & (df["Year"] == year_picker.value)
        & (df["Unit of measure"] == Units.value)
    )
    year_sector_chart = alt.Chart(df.loc[year_sector_mask]).mark_bar().encode(
        y=alt.Y("Country:N"),
        x=alt.X("Value:Q"),
        color=alt.Color('Value:Q', scale=alt.Scale(scheme='plasma')),  # Color based on the 'Value' field with a gradient scheme
        # Tooltips: Show data columns on hover
        tooltip=["Year", "Country", "Measure", "Unit of measure", "Value"],
    ).properties(title="Annual Snapshot of GHG Emissions for a Sector")
    return year_country_chart, year_sector_chart


@app.cell
def _(Country, Units, mo, year_country_chart, year_picker):
    Country_Snapshot = mo.vstack([mo.vstack([year_picker, mo.hstack([Country, Units])]), year_country_chart])
    return (Country_Snapshot,)


@app.cell
def _(Sector, Units, mo, year_picker, year_sector_chart):
    Sector_Snapshot = mo.vstack([mo.vstack([year_picker, mo.hstack([Sector, Units])]), year_sector_chart])
    return (Sector_Snapshot,)


@app.cell
def _(Country_Snapshot, Data, Sector_Snapshot, Trends, mo):
    mo.ui.tabs(
        {
            "Data": Data,
            "Annual Trends": Trends,
            "Annual Snapshot - Country": Country_Snapshot,
            "Annual Snapshot - Sector": Sector_Snapshot,
        }
    )
    return


if __name__ == "__main__":
    app.run()
