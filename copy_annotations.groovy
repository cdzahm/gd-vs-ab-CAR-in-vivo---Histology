/**
 * CAR-T Histology Project
 * Copy tumor annotations from WSCK slides to matched CD3, Caspase-3, and H&E slides
 * Fixed: uses PathObjectTools.transformObject for correct annotation copying
 */

import qupath.lib.objects.PathObjectTools
import qupath.lib.objects.PathObject

def project = getProject()
def imageList = project.getImageList()

def targetStains = ["CD3 (Hu)", "Caspase-3", "H&E"]

int successCount = 0
int failCount = 0
int skippedCount = 0

println "=== Starting annotation copy ==="
println "Total images in project: ${imageList.size()}"
println ""

for (def sourceEntry in imageList) {
    def sourceName = sourceEntry.getImageName()
    
    if (!sourceName.contains("WSCK")) continue
    
    def matcher = sourceName =~ /(\d+-\d+-\d+)\s+WSCK\.czi\s+-\s+(ScanRegion\d+)/
    if (!matcher.matches()) {
        println "WARNING: Could not parse name: ${sourceName}"
        continue
    }
    
    def animalID = matcher[0][1]
    def scanRegion = matcher[0][2]
    
    def sourceData = sourceEntry.readImageData()
    def sourceAnnotations = sourceData.getHierarchy().getAnnotationObjects()
    
    if (sourceAnnotations.isEmpty()) {
        println "SKIPPED: No annotations in ${sourceName}"
        skippedCount++
        continue
    }
    
    println "Processing: ${animalID} ${scanRegion} — ${sourceAnnotations.size()} annotations"
    
    for (def stain in targetStains) {
        def targetNamePattern = "${animalID} ${stain}.czi - ${scanRegion}"
        
        def targetEntry = imageList.find { entry ->
            entry.getImageName() == targetNamePattern
        }
        
        if (targetEntry == null) {
            println "  NOT FOUND: ${targetNamePattern}"
            failCount++
            continue
        }
        
        def targetData = targetEntry.readImageData()
        def targetHierarchy = targetData.getHierarchy()
        
        // Remove existing annotations
        def existingAnnotations = targetHierarchy.getAnnotationObjects()
        if (!existingAnnotations.isEmpty()) {
            targetHierarchy.removeObjects(existingAnnotations, true)
        }
        
        // Copy annotations using PathObjectTools
        def copiedAnnotations = sourceAnnotations.collect { annotation ->
            PathObjectTools.transformObject(annotation, null, true)
        }
        
        targetHierarchy.addObjects(copiedAnnotations)
        targetHierarchy.resolveHierarchy()
        targetEntry.saveImageData(targetData)
        
        println "  COPIED to: ${targetNamePattern}"
        successCount++
    }
}

println ""
println "=== Complete ==="
println "Successful copies: ${successCount}"
println "Failed (not found): ${failCount}"
println "Skipped (no annotations): ${skippedCount}"
