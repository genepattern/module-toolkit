# spatialGE.STenrich Module

## Overview
The spatialGE.STenrich module performs spatial gene set enrichment analysis on spatial transcriptomics data.

## Parameters

### Required Parameters
- **input.file** - Input spatial transcriptomics data file (RDS format)
- **gene.sets.database** - URL or path to gene sets database (GMT format)

### Optional Parameters  
- **permutations** - Number of permutations for statistical testing (default: 1000)
- **random.seed** - Random seed for reproducible results (default: 1234)
- **minimum.spots** - Minimum number of spots required per gene set (default: 5)
- **minimum.genes** - Minimum number of genes required per gene set (default: 10)
- **standard.deviation** - Standard deviation threshold (default: 1.0)

### Output Parameters
- **filter.p.values** - P-value threshold for filtering results (default: 0.05)
- **filter.gene.proportion** - Gene proportion threshold (default: 0.3)

## Usage
This module is designed for analyzing spatial patterns in gene expression data using established gene sets from MSigDB or custom databases.

## Example
```
spatialGE.STenrich(
    input.file = "lung_data.rds",
    gene.sets.database = "h.all.v2024.1.Hs.symbols.gmt",
    permutations = 1000,
    random.seed = 42
)
```
