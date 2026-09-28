class KFP_Actions
{
    static void Remove(ItemBase item,typename actionType)
    {
        ActionBase action=ActionManagerBase.GetAction(actionType);
        if (!action || !item.m_InputActionMap) return;
        array<ActionBase_Basic> actions=item.m_InputActionMap.Get(action.GetInputType());
        if (actions) actions.RemoveItem(action);
    }
};
class KF_PantrySealed: Rice
{
    protected bool m_KFP_Used;
    bool KFP_Used() { return m_KFP_Used; }
    void KFP_MarkUsed() { m_KFP_Used = true; }
    void KFP_ClearUsed() { m_KFP_Used = false; }
    override bool CanBeConsumed(ConsumeConditionData data = null)
    {
        return !m_KFP_Used && ConfigGetBool("kfpDryEdible") && super.CanBeConsumed(data);
    }
    override void SetActions()
    {
        super.SetActions();
        KFP_Actions.Remove(this,ActionEatBig); KFP_Actions.Remove(this,ActionForceFeed);
        if (ConfigGetBool("kfpDryEdible")) AddAction(ActionEatSmall);
        AddAction(KFP_ActionOpen);
        AddAction(KFP_ActionWater);
    }
};
class KF_PantrySnack: Rice {};
class KF_PantryHandSnack: KF_PantrySnack
{
    override void SetActions()
    {
        super.SetActions();
        KFP_Actions.Remove(this,ActionEatBig); AddAction(ActionEatSmall);
    }
};
class KF_PantryDrink: SodaCan_ColorBase
{
    protected bool m_KFP_DrinkOpened;
    void KF_PantryDrink() { RegisterNetSyncVariableBool("m_KFP_DrinkOpened"); }
    bool KFP_IsDrinkOpened() { return m_KFP_DrinkOpened; }
    void KFP_OpenDrink()
    {
        if (!ConfigGetBool("kfpHasClosure") || m_KFP_DrinkOpened) return;
        m_KFP_DrinkOpened=true;
        if (GetGame().IsServer()) SetSynchDirty();
        KFP_UpdateClosure();
    }
    void KFP_UpdateClosure()
    {
        if (ConfigGetBool("kfpHasClosure")) SetAnimationPhase("DrinkOpened",m_KFP_DrinkOpened);
    }
    override void EEInit() { super.EEInit(); KFP_UpdateClosure(); }
    override void OnVariablesSynchronized() { super.OnVariablesSynchronized(); KFP_UpdateClosure(); }
    override void OnStoreSave(ParamsWriteContext ctx)
    {
        super.OnStoreSave(ctx);
        if (ConfigGetBool("kfpHasClosure")) ctx.Write(m_KFP_DrinkOpened);
    }
    override bool OnStoreLoad(ParamsReadContext ctx,int version)
    {
        if (!super.OnStoreLoad(ctx,version)) return false;
        if (ConfigGetBool("kfpHasClosure") && !ctx.Read(m_KFP_DrinkOpened)) m_KFP_DrinkOpened=GetQuantity() < ConfigGetFloat("varQuantityInit");
        return true;
    }
    protected bool m_KFP_DeleteQueued;
    override void OnQuantityChanged(float delta)
    {
        super.OnQuantityChanged(delta);
        if (delta < 0) KFP_OpenDrink();
        KFP_QueueEmptyRemoval();
    }
    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        KFP_UpdateClosure();
        KFP_QueueEmptyRemoval();
    }
    void KFP_QueueEmptyRemoval()
    {
        if (!GetGame().IsServer() || !ConfigGetBool("varQuantityDestroyOnMin") || GetQuantity() > GetQuantityMin() || m_KFP_DeleteQueued) return;
        m_KFP_DeleteQueued=true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(KFP_RemoveEmpty,100,false);
    }
    void KFP_RemoveEmpty()
    {
        m_KFP_DeleteQueued=false;
        if (GetGame().IsServer() && GetQuantity() <= GetQuantityMin()) GetGame().ObjectDelete(this);
    }
    override bool CanBeConsumed(ConsumeConditionData data = null)
    {
        if (GetQuantity() <= GetQuantityMin()) return false;
        return super.CanBeConsumed(data);
    }
};
class KF_PantryBottle: KF_PantryDrink
{
    override void SetActions()
    {
        super.SetActions(); KFP_Actions.Remove(this,ActionDrinkCan); AddAction(ActionDrink);
    }
};
class KF_PantryCarton: KF_PantryDrink
{
    override void SetActions()
    {
        super.SetActions();
        KFP_Actions.Remove(this,ActionDrinkCan);
        AddAction(ActionDrink);
    }
    protected bool m_KFP_PaperQueued;
    protected bool m_KFP_PaperCreated;
    override bool CanBeConsumed(ConsumeConditionData data = null)
    {
        return GetQuantity() > GetQuantityMin() && super.CanBeConsumed(data);
    }
    override void OnQuantityChanged(float delta)
    {
        super.OnQuantityChanged(delta);
        KFP_QueuePaper();
    }
    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        KFP_QueuePaper();
    }
    void KFP_QueuePaper()
    {
        if (!GetGame().IsServer() || GetQuantity() > GetQuantityMin() || m_KFP_PaperQueued || m_KFP_PaperCreated) return;
        m_KFP_PaperQueued = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(KFP_MakePaper,100,false);
    }
    void KFP_MakePaper()
    {
        m_KFP_PaperQueued = false;
        if (!GetGame().IsServer() || m_KFP_PaperCreated || GetQuantity() > GetQuantityMin()) return;
        vector pos = GetPosition();
        PlayerBase owner = PlayerBase.Cast(GetHierarchyRootPlayer());
        if (owner) pos = owner.GetPosition();
        ItemBase paper = ItemBase.Cast(GetGame().CreateObjectEx("Paper",pos,ECE_PLACE_ON_SURFACE));
        if (!paper) return;
        m_KFP_PaperCreated = true;
        if (paper.HasQuantity()) paper.SetQuantity(1);
        paper.SetHealth01("","",GetHealth01("",""));
        GetGame().ObjectDelete(this);
    }
};

class KF_PantryTeaDrink: KF_PantryDrink
{
    override void SetActions()
    {
        super.SetActions();
        KFP_Actions.Remove(this,ActionDrinkCan);
        KFP_Actions.Remove(this,ActionDrink);
        AddAction(KFP_ActionDrinkTea);
    }
    protected int m_KFP_Seconds;
    protected ref Timer m_KFP_Timer;
    void KF_PantryTeaDrink() { RegisterNetSyncVariableInt("m_KFP_Seconds",0,600); }
    void ~KF_PantryTeaDrink() { if (m_KFP_Timer) m_KFP_Timer.Stop(); }
    bool KFP_Ready() { return m_KFP_Seconds == 0; }
    void KFP_Begin(int seconds)
    {
        if (!GetGame().IsServer()) return;
        m_KFP_Seconds = seconds; KFP_Start(); SetSynchDirty();
    }
    void KFP_Start()
    {
        if (!GetGame().IsServer() || m_KFP_Seconds <= 0) return;
        if (!m_KFP_Timer) m_KFP_Timer = new Timer(CALL_CATEGORY_SYSTEM);
        if (!m_KFP_Timer.IsRunning()) m_KFP_Timer.Run(1,this,"KFP_Tick",null,true);
    }
    void KFP_Tick()
    {
        m_KFP_Seconds = Math.Max(0,m_KFP_Seconds - 1);
        if (!m_KFP_Seconds) { m_KFP_Timer.Stop(); SetSynchDirty(); }
    }
    override bool CanBeConsumed(ConsumeConditionData data = null) { return KFP_Ready() && super.CanBeConsumed(data); }
    override bool NameOverride(out string output)
    {
        output = KF_Lang.ConfigText(this, "displayName");
        if (!KFP_Ready()) output += KF_Lang.Text("STR_KF_S_STEEPING");
        return true;
    }
    override void OnStoreSave(ParamsWriteContext ctx) { super.OnStoreSave(ctx); ctx.Write(m_KFP_Seconds); }
    override bool OnStoreLoad(ParamsReadContext ctx,int version)
    {
        if (!super.OnStoreLoad(ctx,version)) return false;
        if (!ctx.Read(m_KFP_Seconds)) return false;
        m_KFP_Seconds = Math.Clamp(m_KFP_Seconds,0,600); return true;
    }
    override void AfterStoreLoad() { super.AfterStoreLoad(); KFP_Start(); SetSynchDirty(); }
};
class KF_PaperCup: Inventory_Base { bool m_KFP_Used; };
class KF_PantryMeal: SpaghettiCan_Opened
{
    protected int m_KFP_Seconds;
    protected ref Timer m_KFP_Timer;
    void KF_PantryMeal() { RegisterNetSyncVariableInt("m_KFP_Seconds",0,600); }
    void ~KF_PantryMeal() { if (m_KFP_Timer) m_KFP_Timer.Stop(); }
    bool KFP_Ready() { return m_KFP_Seconds == 0; }
    void KFP_Begin(int seconds)
    {
        if (!GetGame().IsServer()) return;
        m_KFP_Seconds = seconds; KFP_Start(); SetSynchDirty();
    }
    void KFP_Start()
    {
        if (!GetGame().IsServer() || m_KFP_Seconds <= 0) return;
        if (!m_KFP_Timer) m_KFP_Timer = new Timer(CALL_CATEGORY_SYSTEM);
        if (!m_KFP_Timer.IsRunning()) m_KFP_Timer.Run(1,this,"KFP_Tick",null,true);
    }
    void KFP_Tick()
    {
        m_KFP_Seconds = Math.Max(0,m_KFP_Seconds - 1);
        if (!m_KFP_Seconds) { m_KFP_Timer.Stop(); SetSynchDirty(); }
    }
    override bool CanBeConsumed(ConsumeConditionData data = null) { return KFP_Ready() && super.CanBeConsumed(data); }
    override bool NameOverride(out string output)
    {
        output = KF_Lang.ConfigText(this, "displayName");
        if (!KFP_Ready()) output += KF_Lang.Text("STR_KF_S_SOAKING");
        return true;
    }
    override void OnStoreSave(ParamsWriteContext ctx) { super.OnStoreSave(ctx); ctx.Write(m_KFP_Seconds); }
    override bool OnStoreLoad(ParamsReadContext ctx,int version)
    {
        if (!super.OnStoreLoad(ctx,version)) return false;
        if (!ctx.Read(m_KFP_Seconds)) return false;
        m_KFP_Seconds = Math.Clamp(m_KFP_Seconds,0,600); return true;
    }
    override void AfterStoreLoad() { super.AfterStoreLoad(); KFP_Start(); SetSynchDirty(); }
};
class KF_BibimWet: KF_PreparedNoodles
{
    bool m_KFP_Used;
    override bool CanBeConsumed(ConsumeConditionData data = null) { return false; }
    override void SetActions()
    {
        super.SetActions(); KFP_Actions.Remove(this,KF_ActionEatNoodles); AddAction(KFP_ActionOpen);
    }
    override bool NameOverride(out string output)
    {
        output = KF_Lang.Text("STR_KF_N_PALDOBIBIM");
        if (KF_IsReady()) output += KF_Lang.Text("STR_KF_S_DRAIN");
        else output += KF_Lang.Text("STR_KF_S_SOAKING");
        return true;
    }
};
class KFP_Operations
{
    static bool Owned(ItemBase item, PlayerBase player)
    {
        return item && player && !item.IsRuined() && (!item.GetHierarchyRootPlayer() || item.GetHierarchyRootPlayer() == player);
    }
    static void CopyFood(ItemBase source,ItemBase result)
    {
        result.SetHealth01("","",source.GetHealth01("",""));
        result.SetTemperature(source.GetTemperature());
        result.SetWet(source.GetWet());
        PluginTransmissionAgents transmission = PluginTransmissionAgents.Cast(GetPlugin(PluginTransmissionAgents));
        if (transmission) transmission.TransmitAgents(source,result,AGT_TRANSFER_COPY);
    }
    static bool CanOpen(ItemBase source,PlayerBase player)
    {
        if (!Owned(source,player) || source.ConfigGetString("kfpOpenedType") == "") return false;
        KF_PantrySealed packageItem = KF_PantrySealed.Cast(source);
        KF_BibimWet wet = KF_BibimWet.Cast(source);
        if (packageItem) return !packageItem.KFP_Used();
        if (wet) return !wet.m_KFP_Used && wet.KF_IsReady();
        return false;
    }
    static ItemBase Open(ItemBase source,PlayerBase player)
    {
        if (!GetGame().IsServer() || !CanOpen(source,player)) return null;
        int count = Math.Max(1,source.ConfigGetInt("kfpOpenCount"));
        if (count > 8) return null;
        KF_PantrySealed packageItem = KF_PantrySealed.Cast(source);
        if (packageItem) packageItem.KFP_MarkUsed();
        KF_BibimWet wet = KF_BibimWet.Cast(source);
        if (wet) wet.m_KFP_Used = true;
        array<ItemBase> created = new array<ItemBase>;
        for (int i = 0; i < count; i++)
        {
            ItemBase result = ItemBase.Cast(KF_Cooking.SpawnResult(player,source.ConfigGetString("kfpOpenedType")));
            if (!result)
            {
                foreach (ItemBase rollback:created) GetGame().ObjectDelete(rollback);
                if (packageItem) packageItem.KFP_ClearUsed();
                if (wet) wet.m_KFP_Used = false;
                return null;
            }
            CopyFood(source,result);
            if (!source.ConfigGetBool("kfpDrain")) result.SetQuantity(source.GetQuantity() / count);
            if (count > 1) result.SetPosition(result.GetPosition() + Vector(i * 0.14,0,0));
            created.Insert(result);
        }
        GetGame().ObjectDelete(source); return created[0];
    }

    static bool CanHydrate(KF_PantrySealed source,ItemBase water,PlayerBase player)
    {
        if (!Owned(source,player) || !Owned(water,player) || !KF_Cooking.IsWaterVessel(water)) return false;
        if (source.KFP_Used() || source.ConfigGetString("kfpPreparedType") == "") return false;
        if (source.GetQuantity() + 0.001 < source.ConfigGetFloat("varQuantityInit") || water.GetLiquidType() != LIQUID_WATER) return false;
        return water.GetQuantity() >= source.ConfigGetInt("kfpWaterMl") && water.GetTemperature() >= source.ConfigGetFloat("kfpMinimumTemperature");
    }
    static ItemBase Hydrate(KF_PantrySealed source,ItemBase water,PlayerBase player)
    {
        if (!GetGame().IsServer() || !CanHydrate(source,water,player)) return null;
        ItemBase result = ItemBase.Cast(KF_Cooking.SpawnResult(player,source.ConfigGetString("kfpPreparedType")));
        if (!result) return null;
        source.KFP_MarkUsed(); CopyFood(source,result);
        result.SetTemperature(water.GetTemperature());
        PluginTransmissionAgents transmission = PluginTransmissionAgents.Cast(GetPlugin(PluginTransmissionAgents));
        if (transmission) transmission.TransmitAgents(water,result,AGT_TRANSFER_COPY);
        KF_PantryMeal meal = KF_PantryMeal.Cast(result);
        if (meal) meal.KFP_Begin(source.ConfigGetInt("kfpSoakSeconds"));
        KF_PantryTeaDrink tea = KF_PantryTeaDrink.Cast(result);
        if (tea) tea.KFP_Begin(source.ConfigGetInt("kfpSoakSeconds"));
        water.AddQuantity(-source.ConfigGetInt("kfpWaterMl"));
        GetGame().ObjectDelete(source); return result;
    }
    static bool CanDose(ItemBase powder,ItemBase cup,PlayerBase player)
    {
        if (!Owned(powder,player) || !Owned(cup,player) || cup.GetType() != "KF_PaperCup") return false;
        KF_PaperCup emptyCup = KF_PaperCup.Cast(cup);
        if (!emptyCup || emptyCup.m_KFP_Used) return false;
        KF_PantrySealed packageItem = KF_PantrySealed.Cast(powder);
        return packageItem && !packageItem.KFP_Used() && powder.ConfigGetString("kfpCupType") != "" && powder.GetQuantity() + 0.001 >= powder.ConfigGetFloat("kfpDose");
    }
    static ItemBase Dose(ItemBase powder,ItemBase cup,PlayerBase player)
    {
        if (!GetGame().IsServer() || !CanDose(powder,cup,player)) return null;
        ItemBase result = ItemBase.Cast(KF_Cooking.SpawnResult(player,powder.ConfigGetString("kfpCupType")));
        if (!result) return null;
        // 겹친 종이컵은 1개만 쓴다. 마지막 1개일 때만 재사용을 막고 지운다.
        if (cup.GetQuantity() <= 1) KF_PaperCup.Cast(cup).m_KFP_Used = true;
        CopyFood(powder,result);
        float dose=powder.ConfigGetFloat("kfpDose");
        result.SetQuantity(dose);
        if (powder.GetQuantity() <= dose + 0.001) KF_PantrySealed.Cast(powder).KFP_MarkUsed();
        if (powder.GetQuantity() <= dose + 0.001) GetGame().ObjectDelete(powder);
        else powder.AddQuantity(-dose);
        if (cup.GetQuantity() > 1) cup.AddQuantity(-1);
        else GetGame().ObjectDelete(cup);
        return result;
    }
};
class KFP_ActionOpen: ActionUnpackBox
{
    void KFP_ActionOpen() { m_Text = KF_Lang.Text("STR_KF_A_OPEN"); }
    override bool ActionCondition(PlayerBase player,ActionTarget target,ItemBase item) { return KFP_Operations.CanOpen(item,player); }
    override void OnFinishProgressServer(ActionData action_data) { KFP_Operations.Open(action_data.m_MainItem,action_data.m_Player); }
};
class KFP_ActionWater: ActionContinuousBase
{
    void KFP_ActionWater()
    {
        m_CallbackClass=KF_ActionWaterCB; m_CommandUID=DayZPlayerConstants.CMD_ACTIONFB_CRAFTING;
        m_FullBody=true; m_StanceMask=DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
        m_Text=KF_Lang.Text("STR_KF_A_FILL_WATER");
    }
    override void CreateConditionComponents() { m_ConditionItem=new CCINonRuined; m_ConditionTarget=new CCTObject(UAMaxDistances.DEFAULT); }
    override bool ActionCondition(PlayerBase player,ActionTarget target,ItemBase item)
    {
        return KFP_Operations.CanHydrate(KF_PantrySealed.Cast(item),KF_Cooking.FindVessel(target.GetObject()),player);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        KFP_Operations.Hydrate(KF_PantrySealed.Cast(action_data.m_MainItem),KF_Cooking.FindVessel(action_data.m_Target.GetObject()),action_data.m_Player);
    }
};
class KFP_WaterRecipe: RecipeBase
{
    override void Init()
    {
        m_Name=KF_Lang.Text("STR_KF_R_ADD_WATER"); m_IsInstaRecipe=false; m_AnimationLength=3/CRAFTING_TIME_UNIT_SIZE;
        for (int i=0;i<2;i++) { m_MinDamageIngredient[i]=-1; m_MaxDamageIngredient[i]=3; m_MinQuantityIngredient[i]=-1; m_MaxQuantityIngredient[i]=-1; m_IngredientSetHealth[i]=-1; }
        InsertIngredient(0,"KF_PantrySealed"); InsertIngredient(1,"Pot"); InsertIngredient(1,"Canteen"); InsertIngredient(1,"WaterBottle");
    }
    override bool CanDo(ItemBase ingredients[],PlayerBase player) { return KFP_Operations.CanHydrate(KF_PantrySealed.Cast(ingredients[0]),ingredients[1],player); }
    override void Do(ItemBase ingredients[],PlayerBase player,array<ItemBase> results,float specialty_weight) { KFP_Operations.Hydrate(KF_PantrySealed.Cast(ingredients[0]),ingredients[1],player); }
};
class KFP_CupRecipe: RecipeBase
{
    override void Init()
    {
        m_Name=KF_Lang.Text("STR_KF_R_DOSE"); m_IsInstaRecipe=false; m_AnimationLength=2/CRAFTING_TIME_UNIT_SIZE;
        for (int i=0;i<2;i++) { m_MinDamageIngredient[i]=-1; m_MaxDamageIngredient[i]=3; m_MinQuantityIngredient[i]=-1; m_MaxQuantityIngredient[i]=-1; m_IngredientSetHealth[i]=-1; }
        InsertIngredient(0,"KF_PantrySealed"); InsertIngredient(1,"KF_PaperCup");
    }
    override bool CanDo(ItemBase ingredients[],PlayerBase player) { return KFP_Operations.CanDose(ingredients[0],ingredients[1],player); }
    override void Do(ItemBase ingredients[],PlayerBase player,array<ItemBase> results,float specialty_weight) { KFP_Operations.Dose(ingredients[0],ingredients[1],player); }
};
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions) { super.RegisterActions(actions); actions.Insert(KFP_ActionOpen); actions.Insert(KFP_ActionWater); }
};
modded class PluginRecipesManagerBase
{
    override void RegisterRecipies() { super.RegisterRecipies(); RegisterRecipe(new KFP_WaterRecipe); RegisterRecipe(new KFP_CupRecipe); RegisterRecipe(new KFP_CraftPaperCup); }
};
modded class ModItemRegisterCallbacks
{
    override void RegisterOneHanded(DayZPlayerType pType,DayzPlayerItemBehaviorCfg pBehavior)
    {
        super.RegisterOneHanded(pType,pBehavior);
        pType.AddItemInHandsProfileIK("KF_PantrySealed","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_PantrySnack","dz/anims/workspaces/player/player_main/props/player_main_1h_food_box.asi",pBehavior,"dz/anims/anm/player/ik/gear/rice.anm");
        pType.AddItemInHandsProfileIK("KF_PantryMeal","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/food_can_opened.anm");
        pType.AddItemInHandsProfileIK("KF_PantryHandSnack","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/zagorky.anm");
        pType.AddItemInHandsProfileIK("KF_PantryBottle","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/water_bottle.anm");
        pType.AddItemInHandsProfileIK("KF_PantryCarton","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/water_bottle.anm");
        pType.AddItemInHandsProfileIK("KF_PantryDrink","dz/anims/workspaces/player/player_main/props/player_main_1h_sodacan.asi",pBehavior,"dz/anims/anm/player/ik/gear/soda_can.anm");
        pType.AddItemInHandsProfileIK("KF_PantryTeaDrink","KF_Pantry/anims/tea_drink.asi",pBehavior,"dz/anims/anm/player/ik/gear/soda_can.anm");
        pType.AddItemInHandsProfileIK("KF_PaperCup","dz/anims/workspaces/player/player_main/player_main_1h.asi",pBehavior,"dz/anims/anm/player/ik/gear/food_can_opened.anm");
    }
};


class KF_Nurungji: KF_PantrySealed {};
class KF_NurungjiReady: KF_PantryMeal {};
class KF_ChiliTuna: KF_PantrySealed {};
class KF_ChiliTunaOpen: KF_PantryMeal {};
class KF_FriedKimchi: KF_PantrySealed {};
class KF_FriedKimchiOpen: KF_PantryMeal {};
class KF_CookedRice: KF_PantrySealed {};
class KF_CookedRiceOpen: KF_PantryMeal {};
class KF_DriedSquid: KF_PantrySealed {};
class KF_DriedSquidOpen: KF_PantrySnack {};
class KF_SeasonedGim: KF_PantrySealed {};
class KF_SeasonedGimOpen: KF_PantrySnack {};
class KF_Misutgaru: KF_PantrySealed {};
class KF_MisutgaruCup: KF_PantrySealed {};
class KF_MisutgaruReady: KF_PantryTeaDrink {};
class KF_Jangjorim: KF_PantrySealed {};
class KF_JangjorimOpen: KF_PantryMeal {};
class KF_Perilla: KF_PantrySealed {};
class KF_PerillaOpen: KF_PantryMeal {};
class KF_Mackerel: KF_PantrySealed {};
class KF_MackerelOpen: KF_PantryMeal {};
class KF_Curry: KF_PantrySealed {};
class KF_CurryOpen: KF_PantryMeal {};
class KF_Jjajang: KF_PantrySealed {};
class KF_JjajangOpen: KF_PantryMeal {};


class KF_Yanggaeng: KF_PantrySealed {};
class KF_YanggaengOpen: KF_PantryHandSnack {};
class KF_ChocoPie: KF_PantrySealed {};
class KF_ChocoPieOpen: KF_PantryHandSnack {};
class KF_Hardtack: KF_PantrySealed {};
class KF_HardtackOpen: KF_PantrySnack {};
class KF_CoffeeMix: KF_PantrySealed {};
class KF_CoffeeMixCup: KF_PantrySealed {};
class KF_CoffeeMixReady: KF_PantryTeaDrink {};
class KF_YukgaejangBowl: KF_DryNoodles {};
class KF_YukgaejangBowlReady: KF_PreparedNoodles {};
class KF_KimchiBowl: KF_DryNoodles {};
class KF_KimchiBowlReady: KF_PreparedNoodles {};
class KF_Dosirak: KF_DryNoodles {};
class KF_DosirakReady: KF_PreparedNoodles {};
class KF_KimchiDosirak: KF_DryNoodles {};
class KF_KimchiDosirakReady: KF_PreparedNoodles {};
class KF_AnchovyRiceNoodles: KF_DryNoodles {};
class KF_AnchovyRiceNoodlesReady: KF_PreparedNoodles {};
class KF_LuncheonMeat: KF_PantrySealed {};
class KF_LuncheonMeatOpen: KF_PantryMeal {};
class KF_BeondegiCan: KF_PantrySealed {};
class KF_BeondegiCanOpen: KF_PantryMeal {};
class KF_Whelk: KF_PantrySealed {};
class KF_WhelkOpen: KF_PantryMeal {};
class KF_Cockle: KF_PantrySealed {};
class KF_CockleOpen: KF_PantryMeal {};
class KF_Samgyetang: KF_PantrySealed {};
class KF_SamgyetangOpen: KF_PantryMeal {};
class KF_YukgaejangSoup: KF_PantrySealed {};
class KF_YukgaejangSoupOpen: KF_PantryMeal {};
class KF_BeefSeaweedSoup: KF_PantrySealed {};
class KF_BeefSeaweedSoupOpen: KF_PantryMeal {};
class KF_AbalonePorridge: KF_PantrySealed {};
class KF_AbalonePorridgeOpen: KF_PantryMeal {};
class KF_PumpkinPorridge: KF_PantrySealed {};
class KF_PumpkinPorridgeOpen: KF_PantryMeal {};
class KF_RedBeanPorridge: KF_PantrySealed {};
class KF_RedBeanPorridgeOpen: KF_PantryMeal {};
class KF_BeefVegPorridge: KF_PantrySealed {};
class KF_BeefVegPorridgeOpen: KF_PantryMeal {};
class KF_DoenjangBlock: KF_PantrySealed {};
class KF_DoenjangBlockCup: KF_PantrySealed {};
class KF_DoenjangBlockReady: KF_PantryMeal {};
class KF_EggSoupBlock: KF_PantrySealed {};
class KF_EggSoupBlockCup: KF_PantrySealed {};
class KF_EggSoupBlockReady: KF_PantryMeal {};
class KF_PaldoBibim: KF_DryNoodles {};
class KF_PaldoBibimDrained: KF_PantrySealed {};
class KF_PaldoBibimReady: KF_PreparedNoodles {};
class KF_Neoguri: KF_DryNoodles {};
class KF_NeoguriReady: KF_PreparedNoodles {};
class KF_SesameRamen: KF_DryNoodles {};
class KF_SesameRamenReady: KF_PreparedNoodles {};
class KF_TempuraUdon: KF_DryNoodles {};
class KF_TempuraUdonReady: KF_PreparedNoodles {};
class KF_Jwipo: KF_PantrySealed {};
class KF_JwipoOpen: KF_PantryHandSnack {};
class KF_RoastedBlackSoy: KF_PantrySealed {};
class KF_RoastedBlackSoyOpen: KF_PantrySnack {};
class KF_PineNuts: KF_PantrySealed {};
class KF_PineNutsOpen: KF_PantrySnack {};
class KF_Yugwa: KF_PantrySealed {};
class KF_YugwaOpen: KF_PantrySnack {};
class KF_PeanutGangjeong: KF_PantrySealed {};
class KF_PeanutGangjeongOpen: KF_PantrySnack {};
class KF_Dalgona: KF_PantrySealed {};
class KF_DalgonaOpen: KF_PantryHandSnack {};
class KF_Saewookkang: KF_PantrySealed {};
class KF_SaewookkangOpen: KF_PantrySnack {};
class KF_OjingeoPeanut: KF_PantrySealed {};
class KF_OjingeoPeanutOpen: KF_PantrySnack {};
class KF_Gosomi: KF_PantrySealed {};
class KF_GosomiOpen: KF_PantrySnack {};
class KF_Digestive: KF_PantrySealed {};
class KF_DigestiveOpen: KF_PantryHandSnack {};
class KF_GhanaChocolate: KF_PantrySealed {};
class KF_GhanaChocolateOpen: KF_PantryHandSnack {};
class KF_Pepero: KF_PantrySealed {};
class KF_PeperoOpen: KF_PantryHandSnack {};
class KF_HomeRunBall: KF_PantrySealed {};
class KF_HomeRunBallOpen: KF_PantrySnack {};
class KF_Matdongsan: KF_PantrySealed {};
class KF_MatdongsanOpen: KF_PantrySnack {};
class KF_NutEnergyBar: KF_PantrySealed {};
class KF_NutEnergyBarOpen: KF_PantryHandSnack {};
class KF_Sikhye: KF_PantryDrink {};
class KF_Sujeonggwa: KF_PantryDrink {};
class KF_PearDrink: KF_PantryDrink {};
class KF_BarleyTea: KF_PantrySealed {};
class KF_BarleyTeaCup: KF_PantrySealed {};
class KF_BarleyTeaReady: KF_PantryTeaDrink {};
class KF_Kkokkalcorn: KF_PantrySealed {};
class KF_KkokkalcornOpen: KF_PantrySnack {};
class KF_IonTheFit: KF_PantryBottle {};
class KF_Toreta: KF_PantryBottle {};
class KF_Pocari: KF_PantryBottle {};
class KF_Gatorade: KF_PantryBottle {};
class KF_Powerade: KF_PantryBottle {};
class KF_ChilsungCider: KF_PantryBottle {};
class KF_CeylonTea: KF_PantryDrink {};
class KF_GrapeBongbong: KF_PantryDrink {};
class KF_BananaMilk: KF_PantryBottle {};
class KF_Bacchus: KF_PantryBottle {};
class KF_McCol: KF_PantryDrink {};
class KF_OranC: KF_PantryDrink {};
class KF_Ssaksak: KF_PantryDrink {};
class KF_JuicyCool: KF_PantryCarton {};
class KF_JuicyCoolSmallPeach: KF_PantryCarton {};
class KF_JuicyCoolSmallPineapple: KF_PantryCarton {};
class KF_JuicyCoolSmallGreenGrape: KF_PantryCarton {};
class KF_JuicyCoolLargePlum: KF_PantryCarton {};
class KF_JuicyCoolLargePeach: KF_PantryCarton {};
class KF_JuicyCoolLargePineapple: KF_PantryCarton {};
class KF_JuicyCoolLargeGreenGrape: KF_PantryCarton {};
class KF_SolomonSealTea: KF_PantrySealed {};
class KF_SolomonSealTeaCup: KF_PantrySealed {};
class KF_SolomonSealTeaReady: KF_PantryTeaDrink {};
class KF_CornTea: KF_PantrySealed {};
class KF_CornTeaCup: KF_PantrySealed {};
class KF_CornTeaReady: KF_PantryTeaDrink {};
class KF_CassiaSeedTea: KF_PantrySealed {};
class KF_CassiaSeedTeaCup: KF_PantrySealed {};
class KF_CassiaSeedTeaReady: KF_PantryTeaDrink {};
class KF_Odongtong: KF_DryNoodles {};
class KF_OdongtongReady: KF_PreparedNoodles {};

class KF_SpicySaewookkang: KF_PantrySealed {};
class KF_SpicySaewookkangOpen: KF_PantrySnack {};

class KF_PeperoAlmond: KF_PantrySealed {};

class KF_PeperoAlmondOpen: KF_PantryHandSnack {};

class KF_PeperoChocoFilled: KF_PantrySealed {};

class KF_PeperoChocoFilledOpen: KF_PantryHandSnack {};

class KF_PeperoCrunky: KF_PantrySealed {};

class KF_PeperoCrunkyOpen: KF_PantryHandSnack {};

class KF_PeperoWhiteCookie: KF_PantrySealed {};

class KF_PeperoWhiteCookieOpen: KF_PantryHandSnack {};

class KF_PeperoChocoCookie: KF_PantrySealed {};

class KF_PeperoChocoCookieOpen: KF_PantryHandSnack {};

class KF_HomeRunBallClassic: KF_PantrySealed {};

class KF_HomeRunBallClassicOpen: KF_PantrySnack {};

class KF_HomeRunBallSaltMilk: KF_PantrySealed {};

class KF_HomeRunBallSaltMilkOpen: KF_PantrySnack {};

class KF_KkokkalcornRoasted: KF_PantrySealed {};

class KF_KkokkalcornRoastedOpen: KF_PantrySnack {};

class KF_KkokkalcornSweetSpicy: KF_PantrySealed {};

class KF_KkokkalcornSweetSpicyOpen: KF_PantrySnack {};

class KF_KkokkalcornWaxyCorn: KF_PantrySealed {};

class KF_KkokkalcornWaxyCornOpen: KF_PantrySnack {};

class KF_WhiteGoldCoffee: KF_PantrySealed {};

class KF_WhiteGoldCoffeeCup: KF_PantrySealed
{
    override void EEInit()
    {
        super.EEInit();
        if (GetGame().IsServer()) SetQuantity(ConfigGetFloat("varQuantityInit"));
    }
};

class KF_WhiteGoldCoffeeReady: KF_PantryTeaDrink
{
    override void EEInit()
    {
        super.EEInit();
        if (GetGame().IsServer()) SetQuantity(ConfigGetFloat("varQuantityInit"));
    }
};

class KF_MelonaMilk: KF_PantryBottle {};

class KF_StrawberryMilk: KF_PantryBottle {};

class KF_OranCCalamansi: KF_PantryDrink {};

class KF_OranCOrange: KF_PantryDrink {};

class KF_PearDrinkBottle: KF_PantryBottle {};

class KF_ChestnutYanggaeng: KF_PantrySealed {};

class KF_ChestnutYanggaengOpen: KF_PantryHandSnack {};

class KF_GatoradeZero: KF_PantryBottle {};

class KF_GatoradeBlue: KF_PantryBottle {};

class KF_BacchusF: KF_PantryBottle {};

class KF_SeaweedSoupBlock: KF_PantrySealed {};

class KF_SeaweedSoupBlockCup: KF_PantrySealed {};

class KF_SeaweedSoupBlockReady: KF_PantryMeal {};

class KF_YukgaejangBlock: KF_PantrySealed {};

class KF_YukgaejangBlockCup: KF_PantrySealed {};

class KF_YukgaejangBlockReady: KF_PantryMeal {};

class KF_CurryPouch: KF_PantrySealed {};

class KF_JjajangPouch: KF_PantrySealed {};

class KF_RationKimchiRice: KF_PantrySealed {};

class KF_RationKimchiRiceOpen: KF_PantryMeal {};

class KF_RationWhiteRice: KF_PantrySealed {};

class KF_RationWhiteRiceOpen: KF_PantryMeal {};

class KF_RationMeatballs: KF_PantrySealed {};

class KF_RationMeatballsOpen: KF_PantryMeal {};

class KF_RationTofu: KF_PantrySealed {};

class KF_RationTofuOpen: KF_PantryMeal {};

class KF_RationAnchovy: KF_PantrySealed {};

class KF_RationAnchovyOpen: KF_PantryMeal {};
