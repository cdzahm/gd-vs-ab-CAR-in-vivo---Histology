def project = getProject()
def imageList = project.getImageList()

def outputPath = "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/2025-07-12 In vivo - ab vs gd w Aspc1/Histology/CD3_measurements.csv"

def writer = new File(outputPath).newWriter()
writer.writeLine("Image,Annotation,Area_mm2,Num_Detections,Num_Positive,Positive_Pct,Positive_per_mm2")

for (def entry in imageList) {
    def imageName = entry.getImageName()
    if (!imageName.contains("CD3")) continue
    
    def imageData = entry.readImageData()
    def hierarchy = imageData.getHierarchy()
    def annotations = hierarchy.getAnnotationObjects()
    
    if (annotations.isEmpty()) continue
    
    for (def annotation in annotations) {
        def area = annotation.getROI().getArea()
        def areaMm2 = area / 1e6
        def children = annotation.getChildObjects()
        def numDet = children.size()
        def numPos = children.count { it.getPathClass()?.getName() == "Positive" }
        def posPct = numDet > 0 ? (numPos / numDet * 100) : 0
        def posPmm2 = areaMm2 > 0 ? numPos / areaMm2 : 0
        
        writer.writeLine("${imageName},${annotation.getName()},${areaMm2},${numDet},${numPos},${posPct},${posPmm2}")
    }
}

writer.close()
println "Saved to: ${outputPath}"