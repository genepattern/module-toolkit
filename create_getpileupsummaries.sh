#
# define env variables for GENEPATTERN_USERNAME and GENEPATTERN_PASSWORD
# export GENEPATTERN_USERNAME=ted
# export GENEPATTERN_PASSWORD=
#

python generate-module.py --name gatk.GetPileupSummaries --description "Summarizes counts of reads that support reference, alternate and other alleles for given sites. Results can be used with CalculateContamination." --instructions "Include only the four required arguments. Any other arguments can be passed in using the --arguments_file input to getPipelineSummaries." --language Java --documentation-url https://gatk.broadinstitute.org/hc/en-us/articles/360037593451-GetPileupSummaries  --repository-url https://github.com/broadinstitute/gatk --base-image "broadinstitute/gatk:4.1.4.1"  --gp-user $GENEPATTERN_USERNAME --gp-password $GENEPATTERN_PASSWORD \
  --data /Users/liefeld/Desktop/gatk/normal.bam /Users/liefeld/Desktop/gatk/chr17_small_exac_common_3_grch38.vcf.gz



