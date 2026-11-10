from typing import Dict, List, Any, Optional


def create_skin_shader(
    shader_name: str = "skin_shader",
    albedo_path: str = "",
    roughness_path: str = "",
    pore_height_path: str = "",
    crease_path: str = "",
    normal_vein_path: str = "",
    normal_crease_path: str = "",
    normal_pore_path: str = "",
    normal_composite_path: str = "",
    bump_strength: float = 1.0,
    specular_color: List[float] = [0.8, 0.8, 0.8],
    specular_eccentricity: float = 0.5,
    assign_to: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a blinn skin shader with albedo, roughness, pore/crease bump,
    and vein/crease/pore/composite normal maps, then assign to objects.

    All texture paths are optional — only existing files will be connected.
    Bump sources (pore height, crease, and any enabled normal maps) are
    blended through plusMinusAverage into bump2d → normalCamera.

    Args:
        shader_name: Name for the blinn shader node.
        albedo_path: Path to skin_albedo_uv.png (connected to color).
        roughness_path: Path to skin_roughness_uv.png (specularRollOff).
        pore_height_path: Path to skin_pore_height_uv.png (bump source).
        crease_path: Path to skin_crease_mask_uv.png (bump source / color).
        normal_vein_path: Path to skin_normal_vein_uv.png (bump source).
        normal_crease_path: Path to skin_normal_crease_uv.png (bump source).
        normal_pore_path: Path to skin_normal_pore_uv.png (bump source).
        normal_composite_path: Path to skin_normal_composite_uv.png (bump source).
        bump_strength: bump2d bumpDepth multiplier.
        specular_color: [R, G, B] specular highlight color.
        specular_eccentricity: blinn specular eccentricity.
        assign_to: List of object names to assign the shader to.

    Returns:
        Dict with success flag and created node names.
    """
    import os

    import maya.cmds as cmds

    created_nodes = []

    def _validate_vector3d(vec):
        return (
            isinstance(vec, list)
            and len(vec) == 3
            and all(isinstance(v, (int, float)) for v in vec)
        )

    if not _validate_vector3d(specular_color):
        raise ValueError(
            "Invalid specular_color format. Must be a list of 3 numeric values 0-1."
        )

    # Create/reuse blinn shader
    if cmds.objExists(shader_name):
        shader = shader_name
    else:
        shader = cmds.shadingNode("blinn", asShader=True, name=shader_name)
    created_nodes.append(shader)

    # Set specular color / eccentricity
    r, g, b = specular_color
    cmds.setAttr(f"{shader}.specularColor", r, g, b, type="double3")
    cmds.setAttr(f"{shader}.eccentricity", float(specular_eccentricity))

    # Create/reuse shading group
    sg = f"{shader_name}SG"
    if not cmds.objExists(sg):
        sg = cmds.sets(
            renderable=True, noSurfaceShader=True, empty=True, name=sg
        )
    cmds.connectAttr(f"{shader}.outColor", f"{sg}.surfaceShader")
    created_nodes.append(sg)

    # ---- albedo → color ----
    if albedo_path and os.path.exists(albedo_path):
        albedo_node = "skin_albedo"
        if not cmds.objExists(albedo_node):
            albedo_node = cmds.shadingNode(
                "file", asTexture=True, name=albedo_node
            )
        cmds.connectAttr(f"{albedo_node}.outColor", f"{shader}.color")
        cmds.setAttr(
            f"{albedo_node}.fileTextureName", albedo_path, type="string"
        )
        created_nodes.append(albedo_node)

    # ---- roughness → specularRollOff ----
    if roughness_path and os.path.exists(roughness_path):
        if cmds.attributeQuery("specularRollOff", node=shader, exists=True):
            rough_node = "skin_roughness"
            if not cmds.objExists(rough_node):
                rough_node = cmds.shadingNode(
                    "file", asTexture=True, name=rough_node
                )
            cmds.connectAttr(
                f"{rough_node}.outColorR", f"{shader}.specularRollOff"
            )
            cmds.setAttr(
                f"{rough_node}.fileTextureName", roughness_path, type="string"
            )
            created_nodes.append(rough_node)

    # ---- bump sources: pore height, crease, normal maps ----
    bump_sources = []  # (node_name, file_path)
    if pore_height_path and os.path.exists(pore_height_path):
        bump_sources.append(("skin_pore_height", pore_height_path))
    if crease_path and os.path.exists(crease_path):
        bump_sources.append(("skin_crease_bump", crease_path))
    if normal_vein_path and os.path.exists(normal_vein_path):
        bump_sources.append(("skin_normal_vein", normal_vein_path))
    if normal_crease_path and os.path.exists(normal_crease_path):
        bump_sources.append(("skin_normal_crease", normal_crease_path))
    if normal_pore_path and os.path.exists(normal_pore_path):
        bump_sources.append(("skin_normal_pore", normal_pore_path))
    if normal_composite_path and os.path.exists(normal_composite_path):
        bump_sources.append(("skin_normal_composite", normal_composite_path))

    if bump_sources:
        bump_node = "skin_bump"
        if not cmds.objExists(bump_node):
            bump_node = cmds.shadingNode(
                "bump2d", asUtility=True, name=bump_node
            )
        cmds.connectAttr(f"{bump_node}.outNormal", f"{shader}.normalCamera")
        cmds.setAttr(f"{bump_node}.bumpDepth", float(bump_strength))
        created_nodes.append(bump_node)

        if len(bump_sources) > 1:
            pma = "skin_bump_pma"
            if not cmds.objExists(pma):
                pma = cmds.shadingNode(
                    "plusMinusAverage", asUtility=True, name=pma
                )
                cmds.setAttr(f"{pma}.operation", 1)  # sum
            created_nodes.append(pma)
            for idx, (node_name, fpath) in enumerate(bump_sources):
                if not cmds.objExists(node_name):
                    node_name = cmds.shadingNode(
                        "file", asTexture=True, name=node_name
                    )
                cmds.setAttr(
                    f"{node_name}.fileTextureName", fpath, type="string"
                )
                cmds.connectAttr(
                    f"{node_name}.outAlpha", f"{pma}.input1D[{idx}]"
                )
            cmds.connectAttr(f"{pma}.output1D", f"{bump_node}.bumpValue")
        else:
            node_name, fpath = bump_sources[0]
            if not cmds.objExists(node_name):
                node_name = cmds.shadingNode(
                    "file", asTexture=True, name=node_name
                )
            cmds.connectAttr(f"{node_name}.outAlpha", f"{bump_node}.bumpValue")
            cmds.setAttr(
                f"{node_name}.fileTextureName", fpath, type="string"
            )
            created_nodes.append(node_name)

    # ---- assign to objects ----
    if assign_to:
        for obj in assign_to:
            if cmds.objExists(obj):
                cmds.sets(obj, edit=True, forceElement=sg)

    return {
        "success": True,
        "shader": shader,
        "shading_group": sg,
        "created_nodes": created_nodes,
        "bump_sources": bump_sources,
    }
