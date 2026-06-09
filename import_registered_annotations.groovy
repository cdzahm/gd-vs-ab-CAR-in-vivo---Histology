/**
 * CAR-T Histology Project
 * Import registered GeoJSON annotations into QuPath
 * Fixed for QuPath 0.7 API
 * Run AFTER register_annotations.py has completed
 */

import qupath.lib.io.PathIO
import java.nio.file.Files

def project = getProject()
def imageList = project.getImageList()

def projectPath = project.getPath().getParent()
def registeredDir = projectPath.resolve("geojson_registered")

if (!Files.exists(registeredDir)) {
    println "ERROR: geojson_registered folder not found at ${registeredDir}"
    println "Run register_annotations.py first"
    return
}

println "=== Importing registered annotations ==="
println "Source: ${registeredDir}"
println ""

int imported = 0
int notFound = 0

for (def entry in imageList) {
    def imageName = entry.getImageName()
    
    // Only process target stains (not WSCK)
    if (imageName.contains("WSCK")) continue
    
    // Build expected GeoJSON filename
    def safeFileName = imageName.replaceAll(/[^\w\-. ]/, '_') + ".geojson"
    def geojsonPath = registeredDir.resolve(safeFileName)
    
    if (!Files.exists(geojsonPath)) {
        println "NOT FOUND: ${safeFileName}"
        notFound++
        continue
    }
    
    // Load image data
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    
    // Remove existing annotations
    def existing = hierarchy.getAnnotationObjects()
    if (!existing.isEmpty()) {
        hierarchy.removeObjects(existing, true)
    }
    
    // Import using QuPath 0.7 API — read as stream
    def importedObjects = geojsonPath.toFile().withInputStream { stream ->
        PathIO.readObjectsFromGeoJSON(stream)
    }
    
    hierarchy.addObjects(importedObjects)
    hierarchy.resolveHierarchy()
    entry.saveImageData(imageData)
    
    println "IMPORTED: ${imageName} — ${importedObjects.size()} annotations"
    imported++
}

println ""
println "=== Complete ==="
println "Imported: ${imported}"
println "Not found: ${notFound}"
