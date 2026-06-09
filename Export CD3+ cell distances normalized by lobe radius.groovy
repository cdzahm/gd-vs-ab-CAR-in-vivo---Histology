// Export CD3+ cell distances normalized by lobe radius
// One row per positive cell with mouse ID, lobe area, raw and normalized distance
// Output: CSV to same directory as QuPath project


import qupath.lib.objects.PathAnnotationObject

def project = getProject()
def outputPath = buildFilePath(PROJECT_BASE_DIR, 'cd3_distances.csv')

def writer = new File(outputPath).newWriter()
writer.writeLine("mouse_id,image_name,lobe_id,lobe_area_um2,lobe_radius_um,raw_distance_um,normalized_distance")

for (entry in project.getImageList()) {
    
    def imageName = entry.getImageName()
    
    // Skip non-CD3 images
    if (!imageName.contains("Hu")) continue
    
    // Extract mouse ID e.g. "25-256-13"
    def matcher = imageName =~ /25-256-\d+/
    if (!matcher.find()) {
        println "WARNING: Could not parse mouse ID from ${imageName} — skipping"
        continue
    }
    def mouseId = matcher.group()
    
    println "Processing: ${imageName}"
    
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    def server = imageData.getServer()
    def cal = server.getPixelCalibration()
    double pixelSize = cal.getPixelWidthMicrons()
    double pixelArea = pixelSize * pixelSize

    // Get tumor annotations
    def tumorAnnotations = hierarchy.getAnnotationObjects().findAll {
        it.getPathClass()?.getName() == "Tumor"
    }
    
    if (tumorAnnotations.isEmpty()) {
        println "  WARNING: No Tumor annotations found — skipping"
        continue
    }
    
    // Get CD3+ positive cells
    def positiveCells = hierarchy.getDetectionObjects().findAll {
        it.getPathClass()?.getName() == "Positive"
    }
    
    if (positiveCells.isEmpty()) {
        println "  WARNING: No Positive cells found — skipping"
        continue
    }
    
    // Index annotations by their geometry for point-in-polygon lookup
    def lobeGeometries = tumorAnnotations.collect { it.getROI().getGeometry() }
    
    positiveCells.each { cell ->
        def cellGeom = cell.getROI().getGeometry()
        
        // Find which lobe this cell is inside
        def lobeIndex = lobeGeometries.findIndexOf { it.contains(cellGeom) }
        
        if (lobeIndex < 0) {
            // Cell not inside any lobe — skip (shouldn't happen but just in case)
            return
        }
        
        def lobe = tumorAnnotations[lobeIndex]
        def lobeGeom = lobeGeometries[lobeIndex]
        
        // Lobe area and effective radius
        double lobeAreaUm2 = lobe.getROI().getArea() * pixelArea
        double lobeRadiusUm = Math.sqrt(lobeAreaUm2 / Math.PI)
        
        // Raw distance already stored on cell
        double rawDist = cell.getMeasurementList().get("Distance to Tumor µm")
        
        // Normalized distance (0 = margin, 1 = center)
        double normDist = rawDist / lobeRadiusUm
        
        writer.writeLine([
            mouseId,
            imageName,
            lobeIndex,
            lobeAreaUm2.round(2),
            lobeRadiusUm.round(2),
            rawDist.round(2),
            normDist.round(4)
        ].join(","))
    }
    
    println "  Done — ${positiveCells.size()} positive cells exported"
}

writer.close()
println "Export complete: ${outputPath}"