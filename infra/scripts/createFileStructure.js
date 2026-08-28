import fs from "fs";
import path from "path";
import YAML from "yaml";

const yamlContent = fs.readFileSync("fileStructure.yaml","utf8");


const structure = YAML.parse(yamlContent);

function createStructure(structure,parentPath  =""){
    for(const [name,value] of Object.entries(structure) ){

        const currentPath = path.join(parentPath, name);

        if(value == null){
            fs.writeFileSync(currentPath,"");
        } else{
            fs.mkdirSync(currentPath,{recursive: true});
            createStructure(value,currentPath);
        }
    }
}

createStructure(structure);