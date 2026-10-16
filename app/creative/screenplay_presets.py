"""Fixed, local writing guides for explicitly starting an unsaved screenplay.

This catalog neither creates nor saves a document. Consumers must copy the
chosen document into a new independent draft only after an explicit user
action, replacing every prototype scene ID with a fresh ID. Normal Creative
create/save/history/export remain the owners of the eventual document.

An (id, version) identifies immutable guide content. Changing that content
requires a new version; schema_version describes the catalog envelope only.
All definitions below are immutable tuples of strings. Each call constructs
and validates new original-model instances and returns detached nested data.
"""
from __future__ import annotations

from .models import CreativeDocumentIn, Scene


# Original guidance, not finished fiction, source material, or model output.
# These are linear scene-writing scaffolds, not duration or production plans.
_STARTERS = (
    (
        "FEATURE_FILM",
        "长片剧本",
        "从开场到结局的八场线性写作骨架；按故事需要增删场景，并替换全部提示。",
        (
            ("INT./EXT. [开场地点] - [日/夜]",
             "【写作提示：开场】用可见的动作建立主角的日常、眼前目标和缺失。写出一个具体细节，为结尾的变化留下对照。"),
            ("INT./EXT. [事件发生地] - [日/夜]",
             "【写作提示：诱发事件】写出打破日常的事件，以及主角必须回应的实际问题。让事件通过行动发生，避免用背景说明代替场景。"),
            ("INT./EXT. [决定发生地] - [日/夜]",
             "【写作提示：主动决定】让主角做出带有代价的选择，明确接下来的目标。写出这个决定如何使旧生活无法照常继续。"),
            ("INT./EXT. [阻力发生地] - [日/夜]",
             "【写作提示：阻力升级】安排一次有明确目标的尝试，使阻力或代价增加。写清动作的因果，让结果推动下一场。"),
            ("INT./EXT. [转折发生地] - [日/夜]",
             "【写作提示：中点转折】用一次发现、胜利或失败改变主角对目标的理解。通过新的行动展示策略变化，而不是只解释感受。"),
            ("INT./EXT. [低谷发生地] - [日/夜]",
             "【写作提示：低谷与抉择】让先前选择的后果集中出现。写出主角失去什么，以及继续行动必须放弃或承认什么。"),
            ("INT./EXT. [最终冲突地点] - [日/夜]",
             "【写作提示：高潮】让主角以实际行动面对核心冲突。使决定、代价与结果清楚可见，回应此前建立的目标和变化。"),
            ("INT./EXT. [结局地点] - [日/夜]",
             "【写作提示：余波】用简洁的行动呈现冲突后的生活。回应开场细节，交代必要的结果，给故事留下清晰的结束。"),
        ),
    ),
    (
        "SHORT_FILM",
        "短片剧本",
        "围绕一个核心处境、一次选择和一个结果的四场骨架，适合集中、精简的故事。",
        (
            ("INT./EXT. [核心处境地点] - [日/夜]",
             "【写作提示：建立处境】用一个具体动作交代人物此刻想要什么。限制背景和人物数量，让观众迅速理解这个核心处境。"),
            ("INT./EXT. [打断发生地] - [日/夜]",
             "【写作提示：打断】让一个变化阻碍眼前目标。保持与上一场的直接因果，只保留促使人物作出选择的必要信息。"),
            ("INT./EXT. [选择发生地] - [日/夜]",
             "【写作提示：关键选择】集中描写人物的一次决定及行动。用动作、停顿或必要的对白表达取舍，避免开启新的支线。"),
            ("INT./EXT. [结果呈现地] - [日/夜]",
             "【写作提示：收束】呈现选择带来的直接结果，用一个具体细节回应开场。到变化已经清楚的位置结束，不额外解释主题。"),
        ),
    ),
    (
        "ANIMATION",
        "动画剧本",
        "突出世界规则、形体动作与视觉回环的六场线性骨架，可用于有对白或无对白的动画。",
        (
            ("INT./EXT. [规则展示地点] - [日/夜]",
             "【写作提示：世界规则】通过一个可见的动作展示世界中独特的物理或变形规则。写清动作前后的状态，保持规则可理解。"),
            ("INT./EXT. [愿望发生地] - [日/夜]",
             "【写作提示：角色愿望】用姿态、表情或与物件的互动表现角色的愿望。即使暂时移除对白，也应能看懂角色想做什么。"),
            ("INT./EXT. [尝试发生地] - [日/夜]",
             "【写作提示：动作尝试】安排有准备、执行和结果的动作段落。利用既定世界规则制造阻碍，写清形体与空间关系的变化。"),
            ("INT./EXT. [意外发生地] - [日/夜]",
             "【写作提示：视觉意外】让前一场的动作导致意外结果。可用重复与变化形成趣味，但不要临时增加规则来替角色解决问题。"),
            ("INT./EXT. [解决发生地] - [日/夜]",
             "【写作提示：行动转变】让角色运用已建立的规则，以新的行动回应困难。明确动作的起点、变化和结果，展示角色学到了什么。"),
            ("INT./EXT. [视觉回环地点] - [日/夜]",
             "【写作提示：视觉回环】重访开场的动作、物件或形态，展示关系或意义的变化。让最后的可见动作自然完成故事。"),
        ),
    ),
    (
        "ADVERTISEMENT",
        "广告剧本",
        "按吸引注意、需求、展示、依据和行动邀请组织的五场骨架；产品信息与宣传表述须由作者核实。",
        (
            ("INT./EXT. [注意力入口地点] - [日/夜]",
             "【写作提示：注意力入口】用一个与目标受众相关的具体动作或处境引入主题。先写观众能看到什么，不填入未经确认的品牌或产品信息。"),
            ("INT./EXT. [需求发生地] - [日/夜]",
             "【写作提示：需求】呈现一种具体使用需求及其影响。保持处境可信，避免夸大问题或把假设写成普遍事实。"),
            ("INT./EXT. [产品展示地点] - [日/夜]",
             "【写作提示：展示】写出产品或服务如何被使用，以及可观察到的过程。仅在作者确认后填入名称、功能和实际适用条件。"),
            ("INT./EXT. [依据呈现地点] - [日/夜]",
             "【写作提示：依据】写出支持核心表述的可核实展示及必要限定。由作者核对数据、比较和证言；没有依据时保留待核实提示。"),
            ("INT./EXT. [行动邀请地点] - [日/夜]",
             "【写作提示：行动邀请】用简洁动作或必要的文字提示说明下一步。品牌、渠道、价格和活动条件由作者确认后填写，避免虚构承诺。"),
        ),
    ),
)


def catalog() -> dict:
    """Return the closed v1 catalog with fresh, independently mutable payloads.

    Stable ``starter-...`` scene IDs are catalog prototype identifiers only.
    Callers must replace them when explicitly instantiating an unsaved draft;
    selecting, previewing, or reading this catalog must not save anything.
    """
    templates = []
    for preset_id, title, description, scene_guides in _STARTERS:
        document = CreativeDocumentIn(
            mode="SCREENPLAY",
            title=title,
            source_independent=True,
            scenes=[
                Scene(
                    id=f"starter-{preset_id.lower()}-v1-scene-{sequence:02d}",
                    sequence=sequence,
                    heading=heading,
                    action=action,
                )
                for sequence, (heading, action) in enumerate(scene_guides, start=1)
            ],
        )
        templates.append({
            "id": preset_id,
            "version": 1,
            "title": title,
            "description": description,
            "document": document.model_dump(mode="json"),
        })
    return {"schema_version": 1, "templates": templates}
