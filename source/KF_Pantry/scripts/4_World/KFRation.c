// Production logic independent of packaging geometry.
// Diagnostic fixture names live in a separate config and are never shipped.
class KFR_Sealed: Inventory_Base
{
    bool m_KFR_Used;
    override bool CanBeConsumed(ConsumeConditionData data = null) { return false; }
    override void SetActions()
    {
        super.SetActions();
        AddAction(KFR_ActionOpen);
    }
};
class KFR_OpenBox: Container_Base
{
    override bool CanBeConsumed(ConsumeConditionData data = null) { return false; }
};

class KFR_Operations
{
    static bool CanOpen(KFR_Sealed source,PlayerBase player)
    {
        return source && player && !source.m_KFR_Used && KFP_Operations.Owned(source,player) && source.ConfigGetString("kfrOpenedType") != "";
    }
    static ItemBase Open(KFR_Sealed source,PlayerBase player)
    {
        if (!GetGame().IsServer() || !CanOpen(source,player)) return null;
        array<string> componentTypes = new array<string>;
        source.ConfigGetTextArray("kfrContents",componentTypes);
        if (componentTypes.Count() != 5) return null;
        source.m_KFR_Used = true;
        ItemBase box = ItemBase.Cast(KF_Cooking.SpawnResult(player,source.ConfigGetString("kfrOpenedType")));
        if (!box)
        {
            source.m_KFR_Used = false;
            return null;
        }
        KFP_Operations.CopyFood(source,box);
        foreach (string componentType:componentTypes)
        {
            ItemBase component = ItemBase.Cast(box.GetInventory().CreateInInventory(componentType));
            if (!component)
            {
                GetGame().ObjectDelete(box);
                source.m_KFR_Used = false;
                return null;
            }
            KFP_Operations.CopyFood(source,component);
        }
        GetGame().ObjectDelete(source);
        return box;
    }
};
class KFR_ActionOpen: ActionUnpackBox
{
    void KFR_ActionOpen() { m_Text = KF_Lang.Text("STR_KF_A_OPEN_RATION"); }
    override bool ActionCondition(PlayerBase player,ActionTarget target,ItemBase item)
    {
        return KFR_Operations.CanOpen(KFR_Sealed.Cast(item),player);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        KFR_Operations.Open(KFR_Sealed.Cast(action_data.m_MainItem),action_data.m_Player);
    }
};
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(KFR_ActionOpen);
    }
};

class KF_CombatRation: KFR_Sealed {};
class KF_CombatRationOpen: KFR_OpenBox {};
