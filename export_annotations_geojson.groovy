/**
 * CAR-T Histology Project
 * Export all annotations from all images as GeoJSON files
 * Fixed for QuPath 0.7 API
 */

import qupath.lib.io.PathIO
import java.nio.file.Files
import java.nio.file.Paths

def project = getProject()
def imageList = project.getImageList()

// Create output directory next to project file
def projectPath = project.getPath().getParent()
def exportDir = projectPath.resolve("geojson_export")
Files.createDirectories(exportDir)

println "=== Exporting annotations to GeoJSON ==="
println "Export directory: ${exportDir}"
println "Total images: ${imageList.size()}"
println ""

int exported = 0
int skipped = 0

for (def entry in imageList) {
    def imageName = entry.getImageName()
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    def annotations = hierarchy.getAnnotationObjects()
    
    if (annotations.isEmpty()) {
        println "SKIPPED (no annotations): ${imageName}"
        skipped++
        continue
    }
    
    // Create safe filename from image name
    def safeFileName = imageName.replaceAll(/[^\w\-. ]/, '_') + ".geojson"
    def outputPath = exportDir.resolve(safeFileName)
    
    // Export using correct QuPath 0.7 API
    PathIO.exportObjectsAsGeoJSON(
        outputPath,
        annotations,
        PathIO.GeoJsonExportOptions.PRETTY_JSON
    )
    
    println "EXPORTED: ${imageName} — ${annotations.size()} annotations → ${safeFileName}"
    exported++
}

println ""
println "=== Complete ==="
println "Exported: ${exported}"
println "Skipped: ${skipped}"
println "GeoJSON files at: ${exportDir}"
