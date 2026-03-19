#
# define env variables for GENEPATTERN_USERNAME and GENEPATTERN_PASSWORD
# export GENEPATTERN_USERNAME=ted
# export GENEPATTERN_PASSWORD=
#

python generate-module.py --name gatk.GetPileupSummaries --description "Summarizes counts of reads that support reference, alternate and other alleles for given sites. Results can be used with CalculateContamination." --instructions "Include only the four required arguments. Any other arguments can be passed in using the --arguments_file input to getPipelineSummaries. IMPORTANT: intervals parameter is required as well though it is not specified in the docs, make sure to include it. In tests, the intervals file can be the same as the vcf file.  IMPORTANT: the bam file needs to have a bam index (bai) file passed into GenePattern as a separate file.  In the wrapper script the wrapper must move this into same directory as the bam file before calling gatk  .ALSO IMPORTANT: the vcf file needs to have a vcf index file (*.vcf.gz.tbi) passed into GenePattern as a seperate file. In the wrapper script the wrapper must move the index into the same directory as the vcf file before calling gatk." --language Java --documentation-url https://gatk.broadinstitute.org/hc/en-us/articles/360037593451-GetPileupSummaries  --repository-url https://github.com/broadinstitute/gatk --base-image "broadinstitute/gatk:4.1.4.1"  --gp-user $GENEPATTERN_USERNAME --gp-password $GENEPATTERN_PASSWORD \
  --data /Users/liefeld/Desktop/gatk/normal.bam /Users/liefeld/Desktop/gatk/chr17_small_exac_common_3_grch38.vcf.gz /Users/liefeld/Desktop/gatk/chr17_small_exac_common_3_grch38.vcf.gz.tbi



