// Distance to Tumor Annotation — CD3 Slides Only
// Adds "Distance to Tumor µm" to each detected cell
// Assumes all detections are inside the tumor boundary

import qupath.lib.objects.PathAnnotationObject

def project = getProject()
def imagesToProcess = project.getImageList()

for (entry in imagesToProcess) {
    
    // Skip non-CD3 images
    def imageName = entry.getImageName()
    if (!imageName.contains("Hu")) {
        println "Skipping: ${imageName}"
        continue
    }
    
    println "Processing: ${imageName}"
    
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    def server = imageData.getServer()
    def cal = server.getPixelCalibration()
    double pixelSize = cal.getPixelWidthMicrons()
    
    // Get tumor annotations
    def tumorAnnotations = hierarchy.getAnnotationObjects().findAll {
        it.getPathClass()?.getName() == "Tumor"
    }
    
    if (tumorAnnotations.isEmpty()) {
        println "  WARNING: No Tumor annotation found — skipping"
        continue
    }
    
    // Get all detected cells
   def cells = hierarchy.getDetectionObjects().findAll {
    it.getPathClass()?.getName() == "Positive"
    }
    
    if (cells.isEmpty()) {
        println "  WARNING: No detections found — skipping"
        continue
    }
    
    // Measure distance from each cell centroid to nearest tumor boundary
    cells.each { cell ->
        double minDist = Double.MAX_VALUE
        def cellGeom = cell.getROI().getGeometry()
        
        tumorAnnotations.each { annotation ->
            // .distance() measures to the annotation boundary (perimeter)
            // Returns 0 if the cell is ON the boundary
            double dist = annotation.getROI().getGeometry().getBoundary()
                .distance(cellGeom) * pixelSize
            if (dist < minDist) minDist = dist
        }
        
        cell.getMeasurementList().put("Distance to Tumor µm", minDist)
        cell.getMeasurementList().close()
    }
    
    entry.saveImageData(imageData)
    println "  Done — ${cells.size()} cells measured"
}

println "Batch complete"