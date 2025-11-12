# Load necessary libraries
if (!require("optparse"))  stop("The optparse package is required but is not installed.")
if (!require("spatialGE")) stop("The spatialGE package is required but is not installed.")
if (!require("ggplot2")) stop("The ggplot2 package is required but is not installed.")

library('optparse')
library('spatialGE')
library('ggplot2')

# Parse the command line options
parser = OptionParser()
parser <- add_option(parser, c("-f", "--file"), type = 'character', help = "input.file")
parser <- add_option(parser, c("-g", "--genes"),  type = 'character', help = "genes", default='')
parser <- add_option(parser, c("-s", "--samples"),  type = "character", help = "samples", default='')
parser <- add_option(parser, c("-p", "--palette"),  type = "character", help = "color.palette", default='')
parser <- add_option(parser, c("-c", "--colors"),  type = "character", help = "colors", default='')
parser <- add_option(parser, c("-q", "--points"),  type = 'double', help = "point.size", default=0.0)
parser <- add_option(parser, c("-w", "--ws"),  type = "character", help = "spatial.weights", default='')
parser <- add_option(parser, c("-d", "--dtc"),  type = "character", help = "dynamic.tree.cut", default='dtc')
parser <- add_option(parser, c("-l", "--min"),  type = "integer", help = "minimum.clusters", default=2)
parser <- add_option(parser, c("-i", "--max"),  type = "integer", help = "maximum.clusters", default=5)
parser <- add_option(parser, c("-e", "--ds"),  type = "character", help = "deep.split", default='')
parser <- add_option(parser, c("-j", "--grid"),  type = "character", help = "display.in.grid", default=FALSE)
parser <- add_option(parser, c("-r", "--rows"),  type = "integer", help = "grid.rows", default=3)
parser <- add_option(parser, c("-k", "--columns"),  type = "integer", help = "grid.columns", default=3)
parser <- add_option(parser, c("-m", "--common"),  type = "character", help = "common.legend", default=TRUE)
parser <- add_option(parser, c("-n", "--location"),  type = "character", help = "legend.location", default = "bottom")
args <- parse_args(parser)

# Load the RDS file
data <- readRDS(args$file)

# Process parameters
genes <- if (!is.null(args$genes) & args$genes != "") unlist(strsplit(args$genes, ",")) else NULL
samples <- if (!is.null(args$samples) & args$samples != "") unlist(strsplit(args$samples, ",")) else NULL
palette <- if (!is.null(args$palette) & args$palette != "") args$palette else NULL
colors <- if (!is.null(args$colors) & args$colors != "") unlist(strsplit(args$colors, ",")) else NULL
points <- if (is.null(args$points) | args$points == "" | args$points == 0.0) NULL else args$points
ws <- if (!is.null(args$ws) & args$ws != "") unlist(strsplit(args$ws, ",")) else NULL
ks <- if (tolower(args$dtc) == "false") opt$min:opt$max else 'dtc'
ds <- if (is.null(args$ds) | args$ds == "") NULL else tolower(args$ds) == "true"
grid <- tolower(args$grid) == "true"
common <- tolower(args$common) == "true"


# Call STplot
plots <- STplot(data, genes=genes, samples=samples, color_pal=palette, ptsize=points, ws=ws, ks=ks, deepSplit=ds)

# Arrange plots on a grid
if (grid) {
    grid <- ggpubr::ggarrange(plotlist=plots, nrow=args$rows, ncol=args$columns, common.legend=common, legend=args$location)
    for (i in names(grid)) {
    file_name <- paste0('plots_', i, ".jpg")
        ggsave(file_name, grid[[i]])
    }
} else {
    for (i in names(plots)) {
        file_name <- paste0(i, ".jpg")
        ggsave(file_name, plots[[i]])
    }
}