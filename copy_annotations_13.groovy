/**
 * CAR-T Histology Project
 * Fix script: Copy annotations from 25-256-13 WSCK-014 to matched stain slides
 * Run this separately after the main copy_annotations.groovy script
 */

import qupath.lib.objects.PathObjectTools

def project = getProject()
def imageList = project.getImageList()

// Manual mapping for 25-256-13 which has non-standard filenames
def sourcePattern = "WSCK-014"
def targetPatterns = ["CD3 (Hu)-007", "Caspase-3-010", "H&E-030"]

int successCount = 0

println "=== Fixing 25-256-13 annotations ==="

// Find all WSCK-014 scan regions
def sourceEntries = imageList.findAll { it.getImageName().contains("25-256-13") && it.getImageName().contains("WSCK-014") }

println "Found ${sourceEntries.size()} source scan regions for 25-256-13"

for (def sourceEntry in sourceEntries) {
    def sourceName = sourceEntry.getImageName()
    
    // Extract scan region number
    def matcher = sourceName =~ /ScanRegion(\d+)/
    if (!matcher.find()) continue
    def scanRegion = "ScanRegion${matcher[0][1]}"
    
    def sourceData = sourceEntry.readImageData()
    def sourceAnnotations = sourceData.getHierarchy().getAnnotationObjects()
    
    if (sourceAnnotations.isEmpty()) {
        println "SKIPPED: No annotations in ${sourceName}"
        continue
    }
    
    println "Processing: 25-256-13 ${scanRegion} — ${sourceAnnotations.size()} annotations"
    
    for (def targetPattern in targetPatterns) {
        def targetName = "25-256-13 ${targetPattern}.czi - ${scanRegion}"
        
        def targetEntry = imageList.find { it.getImageName() == targetName }
        
        if (targetEntry == null) {
            println "  NOT FOUND: ${targetName}"
            continue
        }
        
        def targetData = targetEntry.readImageData()
        def targetHierarchy = targetData.getHierarchy()
        
        def existing = targetHierarchy.getAnnotationObjects()
        if (!existing.isEmpty()) targetHierarchy.removeObjects(existing, true)
        
        def copied = sourceAnnotations.collect { PathObjectTools.transformObject(it, null, true) }
        targetHierarchy.addObjects(copied)
        targetHierarchy.resolveHierarchy()
        targetEntry.saveImageData(targetData)
        
        println "  COPIED to: ${targetName}"
        successCount++
    }
}

println ""
println "=== Complete: ${successCount} successful copies ==="
