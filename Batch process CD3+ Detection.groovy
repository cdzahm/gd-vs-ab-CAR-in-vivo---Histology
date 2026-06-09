/**
 * Batch CD3 positive cell detection - threshold 0.5
 */

def project = getProject()
def imageList = project.getImageList()

def paramsJson = '{"detectionImageBrightfield":"Hematoxylin OD","requestedPixelSizeMicrons":0.5,"backgroundRadiusMicrons":8.0,"backgroundByReconstruction":true,"medianRadiusMicrons":0.0,"sigmaMicrons":1.0,"minAreaMicrons":5.0,"maxAreaMicrons":40.0,"threshold":0.05,"maxBackground":2.0,"watershedPostProcess":true,"excludeDAB":true,"cellExpansionMicrons":5.0,"includeNuclei":true,"smoothBoundaries":true,"makeMeasurements":true,"thresholdCompartment":"Cell: DAB OD mean","thresholdPositive1":0.5,"thresholdPositive2":0.6,"thresholdPositive3":0.8,"singleThreshold":true}'

for (def entry in imageList) {
    def imageName = entry.getImageName()
    if (!imageName.contains("CD3")) continue
    if (imageName.contains("25-256-13")) continue
    
    println "Processing: ${imageName}"
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    def annotations = hierarchy.getAnnotationObjects()
    
    if (annotations.isEmpty()) {
        println "  SKIP: no annotations"
        continue
    }
    
    setBatchProjectAndImage(project, imageData)
    hierarchy.getSelectionModel().setSelectedObjects(annotations, null)
    runPlugin('qupath.imagej.detect.cells.PositiveCellDetection', paramsJson)
    
    entry.saveImageData(imageData)
    def nDetections = hierarchy.getDetectionObjects().size()
    println "  Done — ${nDetections} detections"
}

resetBatchProjectAndImage()
println "=== Batch complete ==="