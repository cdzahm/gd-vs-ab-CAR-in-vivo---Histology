// cas3_detection_export.groovy

import qupath.lib.scripting.QP

def outputPath = "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/2025-07-12 In vivo - ab vs gd w Aspc1/Histology/cas3_results.csv"

def writer = new File(outputPath).newPrintWriter()
writer.println("image_name,annotation_name,tumor_area_um2,total_cells,positive_cells,positive_cell_area_um2")

def argsJson = '{"detectionImageBrightfield":"Hematoxylin OD",' +
               '"requestedPixelSizeMicrons":0.5,' +
               '"backgroundRadiusMicrons":8.0,' +
               '"backgroundByReconstruction":true,' +
               '"medianRadiusMicrons":0.0,' +
               '"sigmaMicrons":1.0,' +
               '"minAreaMicrons":10.0,' +
               '"maxAreaMicrons":2000.0,' +
               '"threshold":0.1,' +
               '"maxBackground":2.0,' +
               '"watershedPostProcess":true,' +
               '"excludeDAB":false,' +
               '"cellExpansionMicrons":5.0,' +
               '"includeNuclei":true,' +
               '"smoothBoundaries":false,' +
               '"makeMeasurements":true}'

for (entry in QP.getProject().getImageList()) {

    def imageName = entry.getImageName()

    if (!imageName.contains("Caspase-3")) {
        println "Skipping: ${imageName}"
        continue
    }

    def imageData = entry.readImageData()
    def server = imageData.getServer()
    def hierarchy = imageData.getHierarchy()

    def cal = server.getPixelCalibration()
    def pixelWidth = cal.getPixelWidthMicrons()
    def pixelHeight = cal.getPixelHeightMicrons()

    // Filter by classification instead of name
    def tumorAnnotations = hierarchy.getAnnotationObjects().findAll {
        it.getPathClass()?.getName() == "Tumor"
    }

    if (tumorAnnotations.isEmpty()) {
        println "No Tumor annotation in: ${imageName} — skipping"
        continue
    }

    for (annotation in tumorAnnotations) {

        hierarchy.getSelectionModel().setSelectedObject(annotation, false)

        QP.runPlugin('qupath.imagej.detect.cells.WatershedCellDetection', imageData, argsJson)

        def children = annotation.getChildObjects()

        for (cell in children) {
            def dabMean = cell.getMeasurementList().get("Cell: DAB OD mean")
            if (dabMean != null && dabMean >= 0.5) {
                cell.setPathClass(QP.getPathClass("Positive"))
            } else {
                cell.setPathClass(QP.getPathClass("Negative"))
            }
        }

        def tumorAreaUm2 = annotation.getROI().getArea() * pixelWidth * pixelHeight
        def totalCells = children.size()

        def positiveCells = children.findAll {
            it.getPathClass()?.getName() == "Positive"
        }
        def numPositive = positiveCells.size()

        def positiveCellAreaUm2 = positiveCells.sum { cell ->
            def areaPx = cell.getMeasurementList().get("Cell: Area")
            return (areaPx != null) ? areaPx * pixelWidth * pixelHeight : 0.0
        } ?: 0.0

        writer.println("${imageName},${annotation.getName()},${tumorAreaUm2},${totalCells},${numPositive},${positiveCellAreaUm2}")
        println "Done: ${imageName} | Total: ${totalCells} | Positive: ${numPositive}"
    }

    entry.saveImageData(imageData)
}

writer.close()
println "Export complete: ${outputPath}"