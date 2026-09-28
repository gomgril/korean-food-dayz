class KF_Cooking
{
    static const float MIN_WATER_TEMPERATURE = 80;
    static bool IsWaterVessel(ItemBase item)
    {
        return item && (item.IsKindOf("Pot") || item.IsKindOf("Canteen") || item.IsKindOf("WaterBottle"));
    }
    static ItemBase FindVessel(Object object)
    {
        ItemBase direct = ItemBase.Cast(object);
        if (IsWaterVessel(direct)) return direct;
        EntityAI entity = EntityAI.Cast(object);
        // Cursor may hit the tripod, fireplace or pot.
        for (int depth = 0; entity && depth < 3; depth++)
        {
            FireplaceBase fireplace = FireplaceBase.Cast(entity);
            if (fireplace && IsWaterVessel(fireplace.GetCookingEquipment())) return fireplace.GetCookingEquipment();
            ItemBase attached = ItemBase.Cast(entity.FindAttachmentBySlotName("CookingEquipment"));
            if (IsWaterVessel(attached)) return attached;
            entity = entity.GetHierarchyParent();
        }
        return null;
    }
    static bool CanPrepare(KF_DryNoodles dry, ItemBase water, PlayerBase player)
    {
        if (!dry || !IsWaterVessel(water) || !player || dry.KF_IsUsed() || dry.IsRuined() || water.IsRuined()) return false;
        if (water.GetHierarchyRootPlayer() && water.GetHierarchyRootPlayer() != player) return false;
        if (dry.GetHierarchyRootPlayer() && dry.GetHierarchyRootPlayer() != player) return false;
        if (water.GetLiquidType() != LIQUID_WATER || water.GetTemperature() < MIN_WATER_TEMPERATURE) return false;
        if (water.GetQuantity() < dry.ConfigGetInt("kfWaterMl")) return false;
        return dry.GetQuantity() >= dry.GetQuantityMax();
    }
    static EntityAI SpawnResult(PlayerBase player, string type)
    {
        if (!GetGame().IsServer() || !player) return null;
        vector position = MiscGameplayFunctions.GetRandomizedPositionVerifiedPlayer(player, 0.5, UAItemsSpreadRadius.DEFAULT, player);
        return EntityAI.Cast(GetGame().CreateObjectEx(type, position, ECE_PLACE_ON_SURFACE));
    }
    static KF_PreparedNoodles Prepare(KF_DryNoodles dry, ItemBase water, PlayerBase player)
    {
        if (!GetGame().IsServer() || !CanPrepare(dry, water, player)) return null;
        string resultType = dry.ConfigGetString("kfPreparedType");
        KF_PreparedNoodles result = KF_PreparedNoodles.Cast(SpawnResult(player, resultType));
        if (!result) return null;
        dry.KF_MarkUsed();
        result.SetHealth01("", "", dry.GetHealth01("", ""));
        result.SetTemperature(water.GetTemperature());
        PluginTransmissionAgents transmission = PluginTransmissionAgents.Cast(GetPlugin(PluginTransmissionAgents));
        if (transmission)
        {
            transmission.TransmitAgents(water, result, AGT_TRANSFER_COPY);
            transmission.TransmitAgents(dry, result, AGT_TRANSFER_COPY);
        }
        result.KF_BeginSoaking(dry.ConfigGetInt("kfSoakSeconds"));
        water.SetQuantity(water.GetQuantity() - dry.ConfigGetInt("kfWaterMl"));
        GetGame().ObjectDelete(dry);
        return result;
    }
    static bool HasChopsticks(PlayerBase player)
    {
        array<EntityAI> inventory = new array<EntityAI>;
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, inventory);
        foreach (EntityAI item: inventory)
        {
            if (item.IsKindOf("KF_Chopsticks") && !item.IsRuined()) return true;
        }
        return false;
    }
};
class KF_ActionWaterCB: ActionContinuousBaseCB
{
    override void CreateActionComponent() { m_ActionData.m_ActionComponent = new CAContinuousTime(3); }
};
class KF_ActionTakeHotWater: ActionContinuousBase
{
    void KF_ActionTakeHotWater()
    {
        m_CallbackClass = KF_ActionWaterCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_CRAFTING;
        m_FullBody = true;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
        m_Text = KF_Lang.Text("STR_KF_A_FILL_NOODLE");
    }
    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTObject(UAMaxDistances.DEFAULT);
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        return KF_Cooking.CanPrepare(KF_DryNoodles.Cast(item), KF_Cooking.FindVessel(target.GetObject()), player);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        KF_Cooking.Prepare(KF_DryNoodles.Cast(action_data.m_MainItem), KF_Cooking.FindVessel(action_data.m_Target.GetObject()), action_data.m_Player);
    }
};
class KF_ActionPourHotWater: ActionContinuousBase
{
    void KF_ActionPourHotWater()
    {
        m_CallbackClass = KF_ActionWaterCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_EMPTY_VESSEL;
        m_Text = KF_Lang.Text("STR_KF_A_POUR_NOODLE");
    }
    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTObject(UAMaxDistances.DEFAULT);
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        return KF_Cooking.CanPrepare(KF_DryNoodles.Cast(target.GetObject()), item, player);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        KF_Cooking.Prepare(KF_DryNoodles.Cast(action_data.m_Target.GetObject()), action_data.m_MainItem, action_data.m_Player);
    }
};
class KF_ActionEatDryNoodles: ActionEatSmall
{
    void KF_ActionEatDryNoodles()
    {
        m_Text = KF_Lang.Text("STR_KF_A_EAT_DRY");
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        KF_DryNoodles dry = KF_DryNoodles.Cast(item);
        return dry && dry.ConfigGetBool("kfCanEatDry") && super.ActionCondition(player, target, item);
    }
};
class KF_ActionEatNoodles: ActionEatCan
{
    override void OnStartAnimationLoopClient(ActionData action_data)
    {
        super.OnStartAnimationLoopClient(action_data);
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_StartNoodleLoop();
    }
    override void OnStartAnimationLoopServer(ActionData action_data)
    {
        super.OnStartAnimationLoopServer(action_data);
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_StartNoodleLoop();
    }
    void KF_ActionEatNoodles()
    {
        m_Text = KF_Lang.Text("STR_KF_A_EAT_CHOPSTICKS");
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
    }
    override bool HasProneException() { return false; }
    override void OnStartClient(ActionData action_data)
    {
        super.OnStartClient(action_data);
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_SetEating(true);
    }
    override void OnEndClient(ActionData action_data)
    {
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_SetEating(false);
        super.OnEndClient(action_data);
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(item);
        return meal && meal.KF_IsReady() && KF_Cooking.HasChopsticks(player) && super.ActionCondition(player, target, item);
    }
    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_SetEating(true);
    }
    override void OnEndServer(ActionData action_data)
    {
        KF_PreparedNoodles meal = KF_PreparedNoodles.Cast(action_data.m_MainItem);
        if (meal) meal.KF_SetEating(false);
        super.OnEndServer(action_data);
    }
};
modded class Bottle_Base
{
    override void SetActions() { super.SetActions(); AddAction(KF_ActionPourHotWater); }
};
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(KF_ActionTakeHotWater);
        actions.Insert(KF_ActionPourHotWater);
        actions.Insert(KF_ActionEatNoodles);
        actions.Insert(KF_ActionEatDryNoodles);
    }
};

